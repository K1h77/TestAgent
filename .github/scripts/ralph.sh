#!/bin/bash
set -e

# ==========================================
# CONFIGURATION
# ==========================================
if [ -z "$ISSUE_NUMBER" ]; then
  echo "❌ Error: No Issue Number provided (env var ISSUE_NUMBER missing)."
  exit 1
fi

if [ -z "$GITHUB_REPOSITORY" ]; then
  echo "❌ Error: GITHUB_REPOSITORY env var missing."
  exit 1
fi

REPO="$GITHUB_REPOSITORY"
echo "🤖 [RALPH] Waking up. Target: Issue #$ISSUE_NUMBER in $REPO"

# Ensure we are in the root of the repo
cd "$(git rev-parse --show-toplevel)"
REPO_ROOT="$(pwd)"

# ==========================================
# HELPER FUNCTION: Post Issue Comment
# ==========================================
post_comment() {
  local body="$1"
  gh issue comment "$ISSUE_NUMBER" --repo "$REPO" --body "$body"
}

# ==========================================
# 1. SETUP: Configure Claude (Headless)
# ==========================================
echo "🔧 [RALPH] Configuring Claude Code..."
mkdir -p ~/.config/claude-code

# Use the GitHub MCP server (via Docker) to give Claude native access to issues
cat <<EOF > ~/.config/claude-code/config.json
{
  "mcpServers": {
    "github": {
      "command": "docker",
      "args": [
        "run", 
        "-i", 
        "--rm", 
        "-e", "GITHUB_PERSONAL_ACCESS_TOKEN", 
        "ghcr.io/github/github-mcp-server:latest"
      ],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "$PAT_TOKEN"
      }
    }
  }
}
EOF

# ==========================================
# 2. PLANNING PHASE
# ==========================================
echo "📋 [RALPH] Analyzing Issue..."

# --dangerously-skip-permissions is critical for CI/CD so it doesn't ask for "Y/N"
# -p runs in print (non-interactive) mode

PROMPT_PLAN="I am an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

1. Use the GitHub MCP tools to read the issue details.
2. Explore the codebase to understand the context.
3. Create a detailed step-by-step plan (as a markdown checklist) to solve the issue.
4. Output ONLY the plan in markdown format, starting with '## Plan' as the heading.

IMPORTANT: You have access to Playwright for browser automation and visual testing.
- For any UI, styling, or visual tasks, your plan should include steps to use Playwright to verify the changes.
- You can run '.github/scripts/playwright-screenshot.sh' to start the app, take screenshots, and get a text-based visual summary.
- The visual check script will generate screenshots and a detailed text summary of the UI state (element positions, colors, text content, layout).

Do NOT write code yet. Just output the plan."

PLAN_OUTPUT=$(claude -p "$PROMPT_PLAN" --dangerously-skip-permissions)

echo "📝 [RALPH] Plan created:"
echo "$PLAN_OUTPUT"

# Post plan as issue comment
post_comment "$PLAN_OUTPUT"

# ==========================================
# 2.1. PLAN APPROVAL CHECK
# ==========================================
if [ "$PLAN_APPROVAL_REQUIRED" = "true" ]; then
  echo "⏸️  [RALPH] Plan awaiting approval..."
  post_comment "⏸️ **Plan awaiting approval** — Add the \`plan-approved\` label to continue."
  exit 0
fi

# ==========================================
# 3. CODING ↔ REVIEW LOOP (Max 3 rounds)
# ==========================================
MAX_REVIEW_ROUNDS=3
REVIEW_ROUND=1
REVIEWER_FEEDBACK=""

while [ $REVIEW_ROUND -le $MAX_REVIEW_ROUNDS ]; do
  echo "🔨 [RALPH] Coding Round $REVIEW_ROUND / $MAX_REVIEW_ROUNDS"
  
  # ==========================================
  # 3.1. CODING STEP
  # ==========================================
  if [ $REVIEW_ROUND -eq 1 ]; then
    # First round: just the plan and issue
    PROMPT_CODING="You are an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here is the plan:
$PLAN_OUTPUT

Your task:
1. Use the GitHub MCP tools to read the issue details if needed.
2. Implement ALL items in the plan.
3. Run tests (npm test, pytest, etc.) to verify your changes.
4. Output a summary of what you implemented.

IMPORTANT: You have Playwright available for browser automation and visual testing.
- For UI/styling/visual tasks, use '.github/scripts/playwright-screenshot.sh' to verify your changes visually.
- The script will start the app, take screenshots, and generate a text summary of the visual state.
- Use this to ensure your CSS/HTML changes look correct before finishing.
- Run 'node .github/scripts/visual-check.js' directly if you need more control over the visual testing.

Implement the ENTIRE plan in this single session."
  else
    # Subsequent rounds: include reviewer feedback
    PROMPT_CODING="You are an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here is the original plan:
$PLAN_OUTPUT

The reviewer found issues in your previous implementation:
$REVIEWER_FEEDBACK

Your task:
1. Fix ALL the issues mentioned by the reviewer.
2. Run tests to verify your fixes.
3. Output a summary of what you fixed.

IMPORTANT: You have Playwright available for browser automation and visual testing.
- For UI/styling/visual issues, use '.github/scripts/playwright-screenshot.sh' to verify your fixes.
- The script will generate screenshots and a text summary of the visual state.

Address ALL reviewer concerns in this session."
  fi
  
  CODING_OUTPUT=$(claude -p "$PROMPT_CODING" --dangerously-skip-permissions)
  
  echo "✅ [RALPH] Coding complete for round $REVIEW_ROUND"
  echo "$CODING_OUTPUT"
  
  # Post coding summary as issue comment
  post_comment "## Coding Round $REVIEW_ROUND

$CODING_OUTPUT"
  
  # ==========================================
  # 3.1.1. VISUAL CHECK (if app exists)
  # ==========================================
  VISUAL_SUMMARY=""
  
  if [ -f "$REPO_ROOT/backend/server.js" ]; then
    echo "🎭 [RALPH] Running visual check (optional)..."
    
    # Try to run visual check, but don't fail if it doesn't work
    if bash .github/scripts/playwright-screenshot.sh 2>&1 | tee /tmp/visual-check-output.txt; then
      VISUAL_SUMMARY=$(cat /tmp/visual-check-output.txt)
      echo "✅ [RALPH] Visual check completed"
      
      # Post visual summary as issue comment
      post_comment "## Visual Check Results (Round $REVIEW_ROUND)

\`\`\`
$VISUAL_SUMMARY
\`\`\`"
    else
      echo "⚠️  [RALPH] Visual check failed or not applicable - continuing with code-only review"
      VISUAL_SUMMARY="Visual check was attempted but failed (this is okay - may not be a visual issue)"
    fi
  fi
  
  # ==========================================
  # 3.2. REVIEW STEP
  # ==========================================
  echo "🧐 [RALPH] Starting review for round $REVIEW_ROUND..."
  
  # Get the current git diff (all changes since last commit)
  DIFF_OUTPUT=$(git --no-pager diff HEAD)
  
  # Build review prompt with optional visual summary
  if [ -n "$VISUAL_SUMMARY" ]; then
    PROMPT_REVIEW="You are a Senior Code Reviewer reviewing changes for GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Use the GitHub MCP tools to read the issue details.

Here are the code changes:
\`\`\`diff
$DIFF_OUTPUT
\`\`\`

Visual Check Results (if this is a UI/styling issue):
\`\`\`
$VISUAL_SUMMARY
\`\`\`

Your task:
1. Review the changes against the issue requirements.
2. Check for bugs, security issues, code quality problems, and missing functionality.
3. For UI/styling issues, consider the visual check results - do the changes produce the expected visual output?
4. If the code is good and fully addresses the issue (including visual correctness if applicable), output EXACTLY: 'LGTM'
5. If there are issues, output a detailed numbered list of problems that MUST be fixed.

Be thorough but fair. Output ONLY 'LGTM' or the list of issues."
  else
    PROMPT_REVIEW="You are a Senior Code Reviewer reviewing changes for GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Use the GitHub MCP tools to read the issue details.

Here are the code changes:
\`\`\`diff
$DIFF_OUTPUT
\`\`\`

Your task:
1. Review the changes against the issue requirements.
2. Check for bugs, security issues, code quality problems, and missing functionality.
3. If the code is good and fully addresses the issue, output EXACTLY: 'LGTM'
4. If there are issues, output a detailed numbered list of problems that MUST be fixed.

Be thorough but fair. Output ONLY 'LGTM' or the list of issues."
  fi
  
  REVIEW_OUTPUT=$(claude -p "$PROMPT_REVIEW" --dangerously-skip-permissions)
  
  echo "📋 [RALPH] Review result:"
  echo "$REVIEW_OUTPUT"
  
  # Post review output as issue comment
  post_comment "## Review Round $REVIEW_ROUND

$REVIEW_OUTPUT"
  
  # Check if review passed
  if [[ "$REVIEW_OUTPUT" == *"LGTM"* ]]; then
    echo "✅ [RALPH] Review passed!"
    
    # ==========================================
    # 4. CREATE BRANCH, COMMIT, PUSH, PR
    # ==========================================
    echo "🚀 [RALPH] Creating PR..."
    
    BRANCH_NAME="fix/issue-$ISSUE_NUMBER-auto-$(date +%s)"
    
    # Git Configuration
    git config --global user.email "ralph-bot@users.noreply.github.com"
    git config --global user.name "Ralph Bot"
    
    # Create Branch & Commit
    git checkout -b "$BRANCH_NAME"
    git add .
    git commit -m "Fix: Automated resolution for Issue #$ISSUE_NUMBER"
    
    # Push Branch
    git push origin "$BRANCH_NAME"
    
    # Create PR using gh CLI
    PR_BODY="Closes #$ISSUE_NUMBER

This PR was automatically generated by Ralph, the autonomous coding agent.

## What was done
$CODING_OUTPUT

## Review
$REVIEW_OUTPUT"
    
    gh pr create \
      --repo "$REPO" \
      --base main \
      --head "$BRANCH_NAME" \
      --title "Fix: Issue #$ISSUE_NUMBER (Ralph Agent)" \
      --body "$PR_BODY"
    
    # Post success comment
    post_comment "✅ **Success!** Ralph has completed the work and created a PR.

Review passed after $REVIEW_ROUND round(s)."
    
    echo "🎉 [RALPH] PR Created successfully."
    exit 0
  fi
  
  # Review failed - prepare for next round or fail
  REVIEWER_FEEDBACK="$REVIEW_OUTPUT"
  
  if [ $REVIEW_ROUND -ge $MAX_REVIEW_ROUNDS ]; then
    echo "❌ [RALPH] Failed after $MAX_REVIEW_ROUNDS review rounds."
    
    # Check if there are any changes to push
    if git diff --quiet HEAD; then
      echo "⚠️  [RALPH] No changes to commit."
      
      # Post failure comment without branch
      FAILURE_MSG="❌ **Failed** after $MAX_REVIEW_ROUNDS review rounds.

## Last Review Issues
$REVIEWER_FEEDBACK

## What to do
No code changes were made. The agent may have encountered issues or the problem may require a different approach.

You can:
1. Add the \`ralph-retry\` label to try again
2. Manually implement the changes
3. Close this issue if it's no longer needed"
      
      post_comment "$FAILURE_MSG"
      exit 1
    fi
    
    # Push WIP branch
    BRANCH_NAME="wip/issue-$ISSUE_NUMBER-auto-$(date +%s)"
    
    git config --global user.email "ralph-bot@users.noreply.github.com"
    git config --global user.name "Ralph Bot"
    
    git checkout -b "$BRANCH_NAME"
    git add .
    git commit -m "WIP: Issue #$ISSUE_NUMBER (failed after $MAX_REVIEW_ROUNDS rounds)"
    git push origin "$BRANCH_NAME"
    
    # Post failure comment
    FAILURE_MSG="❌ **Failed** after $MAX_REVIEW_ROUNDS review rounds.

## Last Review Issues
$REVIEWER_FEEDBACK

## What to do
The work-in-progress has been pushed to branch \`$BRANCH_NAME\`.

You can:
1. Review the changes manually and fix the remaining issues
2. Add the \`ralph-retry\` label to try again
3. Close this issue if it's no longer needed"
    
    post_comment "$FAILURE_MSG"
    
    exit 1
  fi
  
  echo "🔄 [RALPH] Review failed. Starting round $((REVIEW_ROUND + 1))..."
  ((REVIEW_ROUND++))
done

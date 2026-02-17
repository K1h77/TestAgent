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
MODEL="openrouter/deepseek/deepseek-chat-v3-0324"
# Maximum lines to include in PR description from coding output
PR_SUMMARY_MAX_LINES=10
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
# HELPER FUNCTION: Summarize Aider Output
# ==========================================
summarize_output() {
  local raw_output="$1"
  local output_type="$2"  # "plan", "coding", or "review"
  
  echo "$raw_output" | sed '/^─\{2,\}$/d' \
    | sed '/^Aider v[0-9]/d' \
    | sed '/^Model:/d' \
    | sed '/^Git repo:/d' \
    | sed '/^Repo-map:/d' \
    | sed '/^Update git /d' \
    | sed '/^Tokens:/d' \
    | sed '/^Cost:/d' \
    | sed '/^https:\/\/aider\.chat/d' \
    | sed '/^The LLM did not conform/d' \
    | sed '/^Applied edit to/d' \
    | sed '/^Commit [0-9a-f]/d' \
    | awk '
      /^<<<<<<< SEARCH/ { skip=1; next }
      /^>>>>>>> REPLACE/ { skip=0; next }
      /^=======$/  { next }
      !skip { print }
    ' \
    | sed '/^[[:space:]]*$/N;/^\n$/d'
}

# ==========================================
# 1. SETUP: Configure Aider
# ==========================================
echo "🔧 [RALPH] Configuring Aider..."
# Aider uses OPENROUTER_API_KEY environment variable automatically

# Fetch issue details to include in prompts
echo "📖 [RALPH] Fetching issue details..."
ISSUE_DETAILS=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json title,body,labels --template '
Title: {{.title}}

Body:
{{.body}}

Labels: {{range $i, $e := .labels}}{{if $i}}, {{end}}{{$e.name}}{{end}}
')

echo "Issue details:"
echo "$ISSUE_DETAILS"

# Download images from issue body for the multimodal model
ISSUE_IMAGES_DIR="/tmp/issue-images"
mkdir -p "$ISSUE_IMAGES_DIR"
IMAGE_ARGS=""
IMG_COUNT=0

# Extract markdown image URLs from issue body
ISSUE_BODY=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json body --jq '.body // ""')
while IFS= read -r img_url; do
  if [ -n "$img_url" ]; then
    IMG_COUNT=$((IMG_COUNT + 1))
    IMG_FILE="$ISSUE_IMAGES_DIR/issue-image-$IMG_COUNT.png"
    if curl -sL -o "$IMG_FILE" "$img_url" 2>/dev/null && [ -s "$IMG_FILE" ]; then
      IMAGE_ARGS="$IMAGE_ARGS --read $IMG_FILE"
      echo "📷 [RALPH] Downloaded issue image $IMG_COUNT: $img_url"
    fi
  fi
done <<< "$(echo "$ISSUE_BODY" | grep -oP '!\[.*?\]\(\K[^)]+' || true)"

if [ $IMG_COUNT -gt 0 ]; then
  echo "📷 [RALPH] Found $IMG_COUNT image(s) in issue body"
else
  echo "📷 [RALPH] No images found in issue body"
fi

# ==========================================
# 2. PLANNING PHASE
# ==========================================
echo "📋 [RALPH] Analyzing Issue..."

# --yes auto-approves all changes for CI/CD (non-interactive mode)
# --model specifies the AI model to use
# --message passes the prompt

PROMPT_PLAN="I am an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

Your task:
1. Read and understand the issue details above.
2. Explore the codebase to understand the context.
3. Create a detailed step-by-step plan (as a markdown checklist) to solve the issue.
4. Output ONLY the plan in markdown format, starting with '## Plan' as the heading.

IMPORTANT: You have access to Playwright for browser automation and visual testing.
- For any UI, styling, or visual tasks, your plan should include steps to use Playwright to verify the changes.
- You can run '.github/scripts/playwright-screenshot.sh' to start the app, take screenshots, and get a text-based visual summary.
- The visual check script will generate screenshots and a detailed text summary of the UI state (element positions, colors, text content, layout).

Do NOT write code yet. Just output the plan."

PLAN_OUTPUT=$(aider --yes --model "$MODEL" $IMAGE_ARGS --message "$PROMPT_PLAN")

echo "📝 [RALPH] Plan created:"
echo "$PLAN_OUTPUT"

# Post plan as issue comment
PLAN_SUMMARY=$(summarize_output "$PLAN_OUTPUT" "plan")
post_comment "## Plan

$PLAN_SUMMARY"

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
FINAL_VISUAL_SUMMARY=""

while [ $REVIEW_ROUND -le $MAX_REVIEW_ROUNDS ]; do
  echo "🔨 [RALPH] Coding Round $REVIEW_ROUND / $MAX_REVIEW_ROUNDS"
  
  # ==========================================
  # 3.1. CODING STEP
  # ==========================================
  if [ $REVIEW_ROUND -eq 1 ]; then
    # First round: just the plan and issue
    PROMPT_CODING="You are an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

Here is the plan:
$PLAN_OUTPUT

Your task:
1. Implement ALL items in the plan.
2. Make sure your changes follow best practices and would pass tests.
3. Output a summary of what you implemented.

IMPORTANT: You have Playwright available for browser automation and visual testing.
- For UI/styling/visual tasks, use '.github/scripts/playwright-screenshot.sh' to verify your changes visually.
- The script will start the app, take screenshots, and generate a text summary of the visual state.
- Use this to ensure your CSS/HTML changes look correct before finishing.
- Run 'node .github/scripts/visual-check.js' directly if you need more control over the visual testing.

Implement the ENTIRE plan in this single session."
  else
    # Subsequent rounds: include reviewer feedback
    PROMPT_CODING="You are an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

Here is the original plan:
$PLAN_OUTPUT

The reviewer found issues in your previous implementation:
$REVIEWER_FEEDBACK

Your task:
1. Fix ALL the issues mentioned by the reviewer.
2. Make sure your fixes follow best practices.
3. Output a summary of what you fixed.

IMPORTANT: You have Playwright available for browser automation and visual testing.
- For UI/styling/visual issues, use '.github/scripts/playwright-screenshot.sh' to verify your fixes.
- The script will generate screenshots and a text summary of the visual state.

Address ALL reviewer concerns in this session."
  fi
  
  # Save current commit SHA before running aider
  BEFORE_SHA=$(git rev-parse HEAD)
  
  CODING_OUTPUT=$(aider --yes --model "$MODEL" $IMAGE_ARGS --message "$PROMPT_CODING")
  
  echo "✅ [RALPH] Coding complete for round $REVIEW_ROUND"
  echo "$CODING_OUTPUT"
  
  # Post coding summary as issue comment
  CODING_SUMMARY=$(summarize_output "$CODING_OUTPUT" "coding")
  # Also list which files were changed
  CHANGED_FILES=$(git diff --name-only "$BEFORE_SHA" HEAD 2>/dev/null | head -20)
  post_comment "## Coding Round $REVIEW_ROUND

$CODING_SUMMARY

### Files Changed
\`\`\`
$CHANGED_FILES
\`\`\`"
  
  # ==========================================
  # 3.1.1. VISUAL CHECK (if app exists)
  # ==========================================
  # Take screenshots for visual verification
  VISUAL_SUMMARY=""
  SCREENSHOT_ARGS=""
  echo "🎭 [RALPH] Taking screenshots..."
  if bash .github/scripts/playwright-screenshot.sh 2>&1 | tee /tmp/ralph-visual-output.txt; then
    VISUAL_SUMMARY=$(cat /tmp/ralph-visual-output.txt)
    # Collect screenshot files for the multimodal reviewer
    for img in "$REPO_ROOT"/screenshots/*.png; do
      [ -f "$img" ] && SCREENSHOT_ARGS="$SCREENSHOT_ARGS --read $img"
    done
    echo "✅ [RALPH] Screenshots taken"
    post_comment "## Visual Check (Round $REVIEW_ROUND)

📸 Screenshots available in workflow artifacts:
https://github.com/$REPO/actions/runs/$GITHUB_RUN_ID"
  else
    echo "⚠️ [RALPH] Screenshots failed - continuing without visual check"
  fi
  rm -f /tmp/ralph-visual-output.txt
  
  # ==========================================
  # 3.2. REVIEW STEP
  # ==========================================
  echo "🧐 [RALPH] Starting review for round $REVIEW_ROUND..."
  
  # Get current commit SHA after aider ran
  AFTER_SHA=$(git rev-parse HEAD)
  
  # Check if aider made any commits
  if [ "$BEFORE_SHA" = "$AFTER_SHA" ]; then
    # No commits were made by aider, check if there are uncommitted changes
    git add -A
    if git diff --cached --quiet; then
      echo "⚠️  [RALPH] No changes detected after coding round."
      post_comment "⚠️ **Warning**: Coding round $REVIEW_ROUND completed but no file changes were detected. Aider may have encountered an issue."
      
      if [ $REVIEW_ROUND -ge $MAX_REVIEW_ROUNDS ]; then
        post_comment "❌ **Failed**: No code changes were made after $MAX_REVIEW_ROUNDS rounds."
        exit 1
      fi
      
      ((REVIEW_ROUND++))
      continue
    fi
  fi
  
  # Get the diff of changes made by aider (compare BEFORE_SHA to current HEAD)
  DIFF_OUTPUT=$(git --no-pager diff "$BEFORE_SHA" HEAD 2>/dev/null || git --no-pager diff --cached)
  
  # Build review prompt
  PROMPT_REVIEW="You are a Senior Code Reviewer reviewing changes for GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

Here are the code changes:
\`\`\`diff
$DIFF_OUTPUT
\`\`\`"

  if [ -n "$VISUAL_SUMMARY" ]; then
    PROMPT_REVIEW="$PROMPT_REVIEW

Visual Check Results:
Screenshots have been taken and are available for your review. Use them to verify the visual correctness of the changes.

\`\`\`
$VISUAL_SUMMARY
\`\`\`"
  fi

  PROMPT_REVIEW="$PROMPT_REVIEW

Your task:
1. Review the changes against the issue requirements.
2. Check for bugs, security issues, code quality problems, and missing functionality.
3. For UI/styling issues, consider the visual check results - do the changes produce the expected visual output?
4. If the code is good and fully addresses the issue (including visual correctness if applicable), output EXACTLY: 'LGTM'
5. If there are issues, output a detailed numbered list of problems that MUST be fixed.

IMPORTANT - Keep your response CONCISE and UNDERSTANDABLE:
- For LGTM: Maximum 2-3 sentences explaining why it looks good
- For issues: 3-5 bullet points maximum, each clearly stating the problem

Be thorough but fair. Output ONLY 'LGTM' (with brief reasoning) or the concise list of issues."
  
  REVIEW_OUTPUT=$(aider --yes --model "$MODEL" $IMAGE_ARGS $SCREENSHOT_ARGS --message "$PROMPT_REVIEW")
  
  echo "📋 [RALPH] Review result:"
  echo "$REVIEW_OUTPUT"
  
  # Post review output as issue comment
  REVIEW_SUMMARY=$(summarize_output "$REVIEW_OUTPUT" "review")
  post_comment "## Review Round $REVIEW_ROUND

$REVIEW_SUMMARY"
  
  # Check if review passed
  if [[ "$REVIEW_OUTPUT" == *"LGTM"* ]]; then
    echo "✅ [RALPH] Review passed!"
    
    # Preserve visual summary from this successful round for PR body
    if [ -n "$VISUAL_SUMMARY" ]; then
      FINAL_VISUAL_SUMMARY="$VISUAL_SUMMARY"
    fi
    
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
    # Extract a brief summary from CODING_OUTPUT (first few lines only)
    BRIEF_SUMMARY=$(echo "$CODING_OUTPUT" | head -n "$PR_SUMMARY_MAX_LINES")
    # Add ellipsis if output was truncated
    if [ "$(echo "$CODING_OUTPUT" | wc -l)" -gt "$PR_SUMMARY_MAX_LINES" ]; then
      BRIEF_SUMMARY="$BRIEF_SUMMARY

...

_(Full details available in workflow logs and issue comments)_"
    fi
    
    PR_BODY="Closes #$ISSUE_NUMBER

This PR was automatically generated by Ralph, the autonomous coding agent.

## Changes Made
$BRIEF_SUMMARY

## Review Status
✅ Code review passed

## Visual Check
📸 Screenshots available in workflow artifacts:
https://github.com/$REPO/actions/runs/$GITHUB_RUN_ID"
    
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
    
    # Summarize feedback for posting
    FEEDBACK_SUMMARY=$(summarize_output "$REVIEWER_FEEDBACK" "review")
    
    # Check if there are any changes to push
    if git diff --quiet HEAD; then
      echo "⚠️  [RALPH] No changes to commit."
      
      # Post failure comment without branch
      FAILURE_MSG="❌ **Failed** after $MAX_REVIEW_ROUNDS review rounds.

## Last Review Issues
$FEEDBACK_SUMMARY

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
$FEEDBACK_SUMMARY

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

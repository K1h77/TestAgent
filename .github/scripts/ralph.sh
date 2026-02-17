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
# HELPER FUNCTION: Extract Summary Section
# ==========================================
extract_summary() {
  local raw_output="$1"
  local marker="$2"  # e.g., "## Summary" or "## Review Summary"
  
  # Extract content from marker line to next ## heading or end of file
  echo "$raw_output" | awk -v marker="${marker}" '
    $0 == marker { found=1; next }
    found && /^## / { exit }
    found { print }
  ' | sed '/^$/d' | head -20
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
# 2. GIT BRANCH SETUP
# ==========================================
echo "🔧 [RALPH] Setting up git branch..."

# Git Configuration - do this early
git config --global user.email "ralph-bot@users.noreply.github.com"
git config --global user.name "Ralph Bot"

# Create feature branch BEFORE coding so Aider commits land on it
BRANCH_NAME="fix/issue-$ISSUE_NUMBER-auto-$(date +%s)"
git checkout -b "$BRANCH_NAME"
echo "✅ [RALPH] Created branch: $BRANCH_NAME"

# ==========================================
# 3. CODING ↔ REVIEW LOOP (Max 3 rounds)
# ==========================================
MAX_REVIEW_ROUNDS=3
REVIEW_ROUND=1
REVIEWER_FEEDBACK=""

# Save initial commit SHA before any changes
INITIAL_SHA=$(git rev-parse HEAD)

while [ $REVIEW_ROUND -le $MAX_REVIEW_ROUNDS ]; do
  echo "🔨 [RALPH] Coding Round $REVIEW_ROUND / $MAX_REVIEW_ROUNDS"
  
  # ==========================================
  # 3.1. CODING STEP
  # ==========================================
  if [ $REVIEW_ROUND -eq 1 ]; then
    # First round: just the issue
    PROMPT_CODING="You are an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

Your task:
1. Read and understand the issue requirements.
2. Explore the codebase to understand the context.
3. Implement the changes to solve the issue.
4. Make sure your changes follow best practices and would pass tests.

IMPORTANT: You MUST run visual verification for any UI/frontend changes.
- After implementing your changes, you MUST run '.github/scripts/playwright-screenshot.sh' to take screenshots of the app.
- This is REQUIRED - the screenshots will be used to verify your work.
- The script will start the app servers, take screenshots, and save them to the screenshots/ directory.
- Do NOT skip this step for any UI-related changes.

End your response with a section that starts with the line '## Summary' (on its own line). In this section, write 2-4 sentences explaining what you changed and why, as if you're a developer posting a progress update to your team. Keep it casual and clear."
  else
    # Subsequent rounds: include reviewer feedback
    PROMPT_CODING="You are an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

The reviewer found issues in your previous implementation:
$REVIEWER_FEEDBACK

Your task:
1. Fix ALL the issues mentioned by the reviewer.
2. Make sure your fixes follow best practices.

IMPORTANT: You MUST run visual verification for any UI/frontend changes.
- After implementing your fixes, you MUST run '.github/scripts/playwright-screenshot.sh' to take screenshots.
- This is REQUIRED - the screenshots will be used to verify your work.

End your response with a section that starts with the line '## Summary' (on its own line). In this section, write 2-4 sentences explaining what you fixed and why, as if you're a developer posting a progress update to your team. Keep it casual and clear."
  fi
  
  # Save current commit SHA before running aider (for this round only)
  BEFORE_ROUND_SHA=$(git rev-parse HEAD)
  
  CODING_OUTPUT=$(aider --yes --model "$MODEL" $IMAGE_ARGS --message "$PROMPT_CODING")
  
  echo "✅ [RALPH] Coding complete for round $REVIEW_ROUND"
  echo "$CODING_OUTPUT"
  
  # Extract the summary section
  CODING_SUMMARY=$(extract_summary "$CODING_OUTPUT" "## Summary")
  
  # If no summary found, use a fallback message
  if [ -z "$CODING_SUMMARY" ]; then
    CODING_SUMMARY="Completed coding changes. See full output in workflow logs."
  fi
  
  # Also list which files were changed (since this round started)
  CHANGED_FILES=$(git diff --name-only "$BEFORE_ROUND_SHA" HEAD 2>/dev/null | head -20)
  if [ -z "$CHANGED_FILES" ]; then
    CHANGED_FILES_DISPLAY="(No committed changes in this round)"
  else
    # Count files properly
    FILE_COUNT=$(echo "$CHANGED_FILES" | grep -c '^')
    # Format the file list (first 10 files only)
    FILES_FORMATTED="$(echo "$CHANGED_FILES" | head -10 | tr '\n' ' ' | sed 's/ $//')"
    
    if [ "$FILE_COUNT" -gt 10 ]; then
      # Show first 10 files and indicate there are more
      REMAINING=$((FILE_COUNT - 10))
      if [ "$REMAINING" -eq 1 ]; then
        CHANGED_FILES_DISPLAY="${FILES_FORMATTED}... and 1 more file"
      else
        CHANGED_FILES_DISPLAY="${FILES_FORMATTED}... and $REMAINING more files"
      fi
    else
      CHANGED_FILES_DISPLAY="$FILES_FORMATTED"
    fi
  fi
  
  post_comment "## Update (Round $REVIEW_ROUND)

$CODING_SUMMARY

**Files changed:** \`$CHANGED_FILES_DISPLAY\`"
  
  # ==========================================
  # 3.1.1. CLEAN UP SCREENSHOTS FROM GIT
  # ==========================================
  # Remove any screenshots that may have been staged/committed
  echo "🧹 [RALPH] Cleaning up screenshots from git..."
  git rm -r --cached screenshots/ 2>/dev/null || true
  git checkout -- .gitignore 2>/dev/null || true
  
  # ==========================================
  # 3.1.2. UPLOAD SCREENSHOTS TO ISSUE COMMENTS
  # ==========================================
  SCREENSHOT_ARGS=""
  SCREENSHOTS_EXIST=false
  
  if [ -d "$REPO_ROOT/screenshots" ] && [ "$(ls -A "$REPO_ROOT/screenshots"/*.png 2>/dev/null)" ]; then
    echo "📸 [RALPH] Found screenshots, uploading to issue..."
    SCREENSHOTS_EXIST=true
    
    # Build comment with uploaded images
    SCREENSHOT_COMMENT="## Screenshots (Round $REVIEW_ROUND)"
    SCREENSHOT_COMMENT="$SCREENSHOT_COMMENT

Screenshots captured after coding changes:
"
    
    # Upload each screenshot and build markdown
    for screenshot_file in "$REPO_ROOT"/screenshots/*.png; do
      if [ -f "$screenshot_file" ]; then
        filename=$(basename "$screenshot_file")
        echo "  Uploading $filename..."
        
        # Try to upload to GitHub using issue comment attachments
        # The most reliable method is to use GitHub's upload-asset endpoint
        # First, we'll try to create a temporary release tag for storing images
        TEMP_TAG="screenshots-issue-${ISSUE_NUMBER}-round-${REVIEW_ROUND}-$(date +%s)"
        IMAGE_URL=""
        
        # Create a lightweight tag and release for storing screenshots
        if gh release create "$TEMP_TAG" --repo "$REPO" --title "Screenshots for Issue #$ISSUE_NUMBER" --notes "Temporary release for screenshot storage" --target "$BRANCH_NAME" 2>/dev/null; then
          # Upload screenshot as release asset
          if gh release upload "$TEMP_TAG" "$screenshot_file" --repo "$REPO" --clobber 2>/dev/null; then
            # Get the asset URL
            IMAGE_URL=$(gh api "repos/$REPO/releases/tags/$TEMP_TAG" --jq ".assets[] | select(.name == \"$filename\") | .browser_download_url" 2>/dev/null)
          fi
        fi
        
        # If upload succeeded, embed the image
        if [ -n "$IMAGE_URL" ]; then
          SCREENSHOT_COMMENT="$SCREENSHOT_COMMENT
![${filename}](${IMAGE_URL})"
          echo "  ✓ Uploaded: $IMAGE_URL"
        else
          # Fallback to artifact reference
          SCREENSHOT_COMMENT="$SCREENSHOT_COMMENT
- 📸 \`$filename\`"
          echo "  ⚠ Could not upload, will reference artifact instead"
        fi
        
        # Collect screenshot files for the multimodal reviewer
        SCREENSHOT_ARGS="$SCREENSHOT_ARGS --read $screenshot_file"
      fi
    done
    
    SCREENSHOT_COMMENT="$SCREENSHOT_COMMENT

View all screenshots in [workflow artifacts](https://github.com/$REPO/actions/runs/$GITHUB_RUN_ID) if images don't load above."
    
    post_comment "$SCREENSHOT_COMMENT"
    echo "✅ [RALPH] Screenshots uploaded to issue"
    
    # Clean up old screenshot releases (older than 7 days)
    echo "🧹 [RALPH] Cleaning up old screenshot releases..."
    SEVEN_DAYS_AGO=$(date -d '7 days ago' +%s 2>/dev/null || date -v-7d +%s 2>/dev/null || echo "0")
    gh api "repos/$REPO/releases" --paginate --jq '.[] | select(.tag_name | startswith("screenshots-issue-")) | {tag: .tag_name, id: .id, created: .created_at}' | \
    while read -r release_data; do
      TAG=$(echo "$release_data" | jq -r '.tag')
      ID=$(echo "$release_data" | jq -r '.id')
      CREATED=$(echo "$release_data" | jq -r '.created')
      CREATED_TS=$(date -d "$CREATED" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%SZ" "$CREATED" +%s 2>/dev/null || echo "0")
      if [ "$CREATED_TS" -lt "$SEVEN_DAYS_AGO" ] && [ "$CREATED_TS" != "0" ]; then
        echo "  Deleting old release: $TAG (created $CREATED)"
        gh release delete "$TAG" --repo "$REPO" --yes 2>/dev/null || true
      fi
    done 2>/dev/null || true
  else
    echo "ℹ️  [RALPH] No screenshots found in screenshots/ directory"
  fi
  
  # ==========================================
  # 3.2. REVIEW STEP
  # ==========================================
  echo "🧐 [RALPH] Starting review for round $REVIEW_ROUND..."
  
  # Get current commit SHA after aider ran
  AFTER_ROUND_SHA=$(git rev-parse HEAD)
  
  # Check if aider made any commits in this round
  if [ "$BEFORE_ROUND_SHA" = "$AFTER_ROUND_SHA" ]; then
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
  
  # Get the diff of changes made by aider in this round
  DIFF_OUTPUT=$(git --no-pager diff "$BEFORE_ROUND_SHA" HEAD 2>/dev/null || git --no-pager diff --cached)
  
  # Build review prompt
  PROMPT_REVIEW="You are a Senior Code Reviewer reviewing changes for GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

Here are the code changes:
\`\`\`diff
$DIFF_OUTPUT
\`\`\`"

  if [ "$SCREENSHOTS_EXIST" = true ]; then
    PROMPT_REVIEW="$PROMPT_REVIEW

Visual Verification:
Screenshots of the application have been provided to you for review. Use them to verify the visual correctness of the changes."
  else
    PROMPT_REVIEW="$PROMPT_REVIEW

Visual Verification:
No visual verification was performed for this round. Review based on code changes only. Do NOT claim you verified the visual appearance."
  fi

  PROMPT_REVIEW="$PROMPT_REVIEW

Your task:
1. Review the changes against the issue requirements.
2. Check for bugs, security issues, code quality problems, and missing functionality.
3. For UI/styling issues, consider whether visual verification is needed and available.
4. If the code is good and fully addresses the issue (including visual correctness if applicable), output EXACTLY: 'LGTM'
5. If there are issues, output a detailed numbered list of problems that MUST be fixed.

End your response with a section that starts with the line '## Review Summary' (on its own line). In this section:
- If LGTM: Write 2-3 sentences explaining why it looks good
- If issues found: Write 3-5 bullet points maximum, each clearly stating the problem

Be thorough but fair. Make sure to include the '## Review Summary' section at the end of your response."
  
  REVIEW_OUTPUT=$(aider --yes --model "$MODEL" $IMAGE_ARGS $SCREENSHOT_ARGS --message "$PROMPT_REVIEW")
  
  echo "📋 [RALPH] Review result:"
  echo "$REVIEW_OUTPUT"
  
  # Extract the review summary section
  REVIEW_SUMMARY=$(extract_summary "$REVIEW_OUTPUT" "## Review Summary")
  
  # If no summary found, use a fallback
  if [ -z "$REVIEW_SUMMARY" ]; then
    REVIEW_SUMMARY="Review completed. See full output in workflow logs."
  fi
  
  post_comment "## Review (Round $REVIEW_ROUND)

$REVIEW_SUMMARY"
  
  # Check if review passed
  if [[ "$REVIEW_OUTPUT" == *"LGTM"* ]]; then
    echo "✅ [RALPH] Review passed!"
    
    # ==========================================
    # 4. PUSH BRANCH AND CREATE PR
    # ==========================================
    echo "🚀 [RALPH] Creating PR..."
    
    # Check if any commits were made across all rounds, if not and there are changes, commit them
    FINAL_SHA=$(git rev-parse HEAD)
    if [ "$INITIAL_SHA" = "$FINAL_SHA" ]; then
      # No commits were made by Aider, check for uncommitted changes
      git add -A
      if ! git diff --cached --quiet; then
        echo "📝 [RALPH] Committing uncommitted changes..."
        git commit -m "Fix: Automated resolution for Issue #$ISSUE_NUMBER"
      fi
    fi
    
    # Push the branch (with Aider's commits)
    git push origin "$BRANCH_NAME"
    
    # Create PR using gh CLI
    # Extract a brief summary from CODING_SUMMARY
    BRIEF_SUMMARY="$CODING_SUMMARY"
    
    PR_BODY="Closes #$ISSUE_NUMBER

This PR was automatically generated by Ralph, the autonomous coding agent.

## Changes Made
$BRIEF_SUMMARY

## Review Status
✅ Code review passed

## Screenshots
See issue comments for visual verification screenshots, or download from [workflow artifacts](https://github.com/$REPO/actions/runs/$GITHUB_RUN_ID)"
    
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
    
    # Check if there are any changes to push (across all rounds)
    FINAL_SHA=$(git rev-parse HEAD)
    if [ "$INITIAL_SHA" = "$FINAL_SHA" ]; then
      # No commits by Aider across all rounds, check for uncommitted changes
      git add -A
      if git diff --cached --quiet; then
        echo "⚠️  [RALPH] No changes to commit."
        
        # Post failure comment without branch
        FAILURE_MSG="❌ **Failed** after $MAX_REVIEW_ROUNDS review rounds.

## Last Review Issues
$REVIEW_SUMMARY

## What to do
No code changes were made. The agent may have encountered issues or the problem may require a different approach.

You can:
1. Add the \`ralph-retry\` label to try again
2. Manually implement the changes
3. Close this issue if it's no longer needed"
        
        post_comment "$FAILURE_MSG"
        exit 1
      else
        # Commit the uncommitted changes
        git commit -m "WIP: Issue #$ISSUE_NUMBER (failed after $MAX_REVIEW_ROUNDS rounds)"
      fi
    fi
    
    # Push WIP branch (we're already on the feature branch)
    git push origin "$BRANCH_NAME"
    
    # Post failure comment
    FAILURE_MSG="❌ **Failed** after $MAX_REVIEW_ROUNDS review rounds.

## Last Review Issues
$REVIEW_SUMMARY

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

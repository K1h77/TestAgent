#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../configure-ralph"

validate_environment() {
  if [ -z "$ISSUE_NUMBER" ]; then
    echo "❌ Error: No Issue Number provided (env var ISSUE_NUMBER missing)."
    exit 1
  fi
  if [ -z "$GITHUB_REPOSITORY" ]; then
    echo "❌ Error: GITHUB_REPOSITORY env var missing."
    exit 1
  fi
}

initialize_configuration() {
  REPO="$GITHUB_REPOSITORY"
  MODEL_ARCHITECT="$RALPH_MODEL_ARCHITECT"
  MODEL_CODER="$RALPH_MODEL_CODER"
  MODEL_REVIEWER="$RALPH_MODEL_REVIEWER"
  PR_SUMMARY_MAX_LINES="$RALPH_PR_SUMMARY_MAX_LINES"
  MAX_REVIEW_ROUNDS="$RALPH_MAX_REVIEW_ROUNDS"
  echo "🤖 [RALPH] Waking up. Target: Issue #$ISSUE_NUMBER in $REPO"
}

navigate_to_repo_root() {
  cd "$(git rev-parse --show-toplevel)"
  REPO_ROOT="$(pwd)"
}

post_comment() {
  local body="$1"
  gh issue comment "$ISSUE_NUMBER" --repo "$REPO" --body "$body"
}

extract_summary() {
  local raw_output="$1"
  local marker="$2"
  echo "$raw_output" | awk -v marker="${marker}" '
    $0 == marker { found=1; next }
    found && /^## / { exit }
    found { print }
  ' | sed '/^$/d' | head -"$RALPH_SUMMARY_MAX_LINES"
}

preprocess_issue_details() {
  echo "🔧 [RALPH] Configuring Aider..."
  source "$SCRIPT_DIR/pre-process-issue.sh"
}

resolve_test_commands() {
  TEST_COMMANDS=()
  AIDER_TEST_FLAGS=""
  
  if [ -z "$ISSUE_LABELS" ]; then
    echo "ℹ️  [RALPH] No issue labels found, skipping test command resolution"
    return
  fi
  
  echo "🧪 [RALPH] Resolving test commands from labels: $ISSUE_LABELS"
  
  # Split comma-separated labels and process each
  IFS=',' read -ra LABELS <<< "$ISSUE_LABELS"
  for label in "${LABELS[@]}"; do
    # Trim whitespace, uppercase, and replace non-alphanumeric chars with underscore
    label=$(echo "$label" | xargs | tr '[:lower:]' '[:upper:]' | sed 's/[^A-Z0-9_]/_/g')
    
    # Check if RALPH_TEST_CMD_<LABEL> is set
    var_name="RALPH_TEST_CMD_${label}"
    test_cmd="${!var_name}"
    
    if [ -n "$test_cmd" ]; then
      echo "  ✅ Found test command for '$label': $test_cmd"
      TEST_COMMANDS+=("$test_cmd")
    fi
  done
  
  # Build aider flags if we have test commands
  if [ ${#TEST_COMMANDS[@]} -gt 0 ]; then
    AIDER_TEST_FLAGS="--auto-test"
    for cmd in "${TEST_COMMANDS[@]}"; do
      AIDER_TEST_FLAGS="$AIDER_TEST_FLAGS --test-cmd \"$cmd\""
    done
    echo "✅ [RALPH] Test automation enabled with ${#TEST_COMMANDS[@]} command(s)"
  else
    echo "ℹ️  [RALPH] No matching test commands found for labels"
  fi
}

apply_difficulty_overrides() {
  if [ -z "$ISSUE_LABELS" ]; then
    return
  fi

  IFS=',' read -ra LABELS <<< "$ISSUE_LABELS"
  for label in "${LABELS[@]}"; do
    label=$(echo "$label" | xargs | tr '[:lower:]' '[:upper:]')
    if [ "$label" = "HARD" ] && [ -n "$RALPH_MODEL_ARCHITECT_HARD" ]; then
      echo "🔥 [RALPH] 'hard' label detected — upgrading architect to $RALPH_MODEL_ARCHITECT_HARD"
      MODEL_ARCHITECT="$RALPH_MODEL_ARCHITECT_HARD"
      return
    fi
  done
}

build_issue_image_flags() {
  ISSUE_IMAGE_FLAGS=""
  
  if [ ! -d "$ISSUE_IMAGES_DIR" ]; then
    return
  fi
  
  local img_count=0
  for img_file in "$ISSUE_IMAGES_DIR"/*.png; do
    if [ -f "$img_file" ]; then
      ISSUE_IMAGE_FLAGS="$ISSUE_IMAGE_FLAGS --file \"$img_file\""
      img_count=$((img_count + 1))
    fi
  done
  
  if [ $img_count -gt 0 ]; then
    echo "🖼️  [RALPH] Will pass $img_count image(s) to aider for multi-modal architect"
  fi
}

configure_git_user() {
  echo "🔧 [RALPH] Setting up git branch..."
  git config --global user.email "$RALPH_BOT_EMAIL"
  git config --global user.name "$RALPH_BOT_NAME"
}

create_feature_branch() {
  BRANCH_NAME="$RALPH_BRANCH_PREFIX-$ISSUE_NUMBER-auto-$(date +%s)"
  git checkout -b "$BRANCH_NAME"
  echo "✅ [RALPH] Created branch: $BRANCH_NAME"
}

initialize_loop_state() {
  REVIEW_ROUND=1
  REVIEWER_FEEDBACK=""
  INITIAL_SHA=$(git rev-parse HEAD)
}

run_test_scaffolding() {
  # Only run if we have test commands
  if [ -z "$AIDER_TEST_FLAGS" ]; then
    echo "ℹ️  [RALPH] Skipping test scaffolding (no test commands configured)"
    return
  fi
  
  echo "🧪 [RALPH] Step 0: Test Scaffolding"
  echo "Creating/updating tests to capture acceptance criteria..."
  
  local test_prompt="You are an autonomous agent preparing tests for GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

Your task:
1. Explore the existing test files in the codebase.
2. Remove any tests that are now outdated or irrelevant to this issue.
3. Write NEW failing unit tests that capture the acceptance criteria of this issue.
4. The tests should fail initially because the feature is not yet implemented.
5. Do NOT implement the actual feature - ONLY write/update tests.

IMPORTANT: Focus on test quality:
- Tests should be specific and verify the exact behavior described in the issue
- Use clear, descriptive test names
- Follow existing test patterns and conventions in the codebase
- Make sure tests will fail initially (red phase of TDD)

End your response with a section that starts with the line '## Summary' (on its own line). Briefly describe what tests you added/removed and why."
  
  # Run aider without --auto-test (we expect tests to fail at this stage)
  eval "aider --yes-always --architect --model \"$MODEL_ARCHITECT\" --editor-model \"$MODEL_CODER\" $ISSUE_IMAGE_FLAGS --message \"$test_prompt\""
  
  local test_summary="Test scaffolding complete. Tests have been prepared to capture the acceptance criteria."
  post_comment "🧪 **Test Scaffolding Complete**

$test_summary

Next: Implementing the feature to make these tests pass."
  
  echo "✅ [RALPH] Test scaffolding complete"
}

build_initial_coding_prompt() {
  local test_context=""
  if [ ${#TEST_COMMANDS[@]} -gt 0 ]; then
    test_context="\n\nNOTE: Failing unit tests have already been written to capture the acceptance criteria of this issue. Your implementation must make these tests pass."
  fi
  
  echo "You are an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details. Any images in the issue have been provided to you directly - use them to understand visual requirements:
$ISSUE_DETAILS$test_context

Your task:
1. Read and understand the issue requirements.
2. Explore the codebase to understand the context.
3. Implement the changes to solve the issue.
4. Make sure your changes follow best practices and pass all tests.

IMPORTANT: You MUST run visual verification for any UI/frontend changes.
- Before taking screenshots, inspect the codebase (e.g. frontend routes, server routes, index.html, app.js, etc.) 
- Set the SCREENSHOT_PAGES environment variable to a comma-separated list of the relevant routes that have been changed or are relevant to the issue when running the script.
  Example: SCREENSHOT_PAGES='/, /about, /settings' bash .github/scripts/playwright-screenshot.sh
- If you can only find the root page, just use '/'. But always check first.
- This is REQUIRED - the screenshots will be used to verify your work.
- The script will start the app servers, take screenshots, and save them to the screenshots/ directory.
- Do NOT skip this step for any UI-related changes.

End your response with a section that starts with the line '## Summary' (on its own line). In this section, write 2-4 sentences explaining what you changed and why, as if you're a developer posting a progress update to your team. Keep it casual and clear."
}

build_revision_coding_prompt() {
  local test_context=""
  if [ ${#TEST_COMMANDS[@]} -gt 0 ]; then
    test_context="\n\nREMINDER: All tests must pass. The unit tests capture the acceptance criteria."
  fi
  
  echo "You are an autonomous agent working on GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details. Any images in the issue have been provided to you directly - use them to understand visual requirements:
$ISSUE_DETAILS

The reviewer found issues in your previous implementation:
$REVIEWER_FEEDBACK$test_context

Your task:
1. Fix ALL the issues mentioned by the reviewer.
2. Make sure your fixes follow best practices and pass all tests.

IMPORTANT: You MUST run visual verification for any UI/frontend changes.
- Before taking screenshots, inspect the codebase (e.g. frontend routes, server routes, index.html, app.js, etc.) to discover ALL pages/routes the app serves.
- Set the SCREENSHOT_PAGES environment variable to a comma-separated list of those routes when running the script.
  Example: SCREENSHOT_PAGES='/, /about, /settings' bash .github/scripts/playwright-screenshot.sh
- If you can only find the root page, just use '/'. But always check first.
- This is REQUIRED - the screenshots will be used to verify your work.

End your response with a section that starts with the line '## Summary' (on its own line). In this section, write 2-4 sentences explaining what you fixed and why, as if you're a developer posting a progress update to your team. Keep it casual and clear."
}

run_aider_coding() {
  local prompt="$1"
  eval "aider --yes-always --architect --model \"$MODEL_ARCHITECT\" --editor-model \"$MODEL_CODER\" $ISSUE_IMAGE_FLAGS $AIDER_TEST_FLAGS --message \"$prompt\""
}

get_coding_summary() {
  local coding_output="$1"
  local summary=$(extract_summary "$coding_output" "## Summary")
  if [ -z "$summary" ]; then
    echo "Completed coding changes. See full output in workflow logs."
  else
    echo "$summary"
  fi
}

extract_changed_files() {
  local before_sha="$1"
  git diff --name-only "$before_sha" HEAD 2>/dev/null | head -"$RALPH_CHANGED_FILES_MAX"
}

format_changed_files_display() {
  local changed_files="$1"
  if [ -z "$changed_files" ]; then
    echo "(No committed changes in this round)"
    return
  fi
  
  local file_count=$(echo "$changed_files" | grep -c '^')
  local files_formatted="$(echo "$changed_files" | head -"$RALPH_CHANGED_FILES_DISPLAY" | tr '\n' ' ' | sed 's/ $//') "
  
  if [ "$file_count" -gt "$RALPH_CHANGED_FILES_DISPLAY" ]; then
    local remaining=$((file_count - RALPH_CHANGED_FILES_DISPLAY))
    if [ "$remaining" -eq 1 ]; then
      echo "${files_formatted}... and 1 more file"
    else
      echo "${files_formatted}... and $remaining more files"
    fi
  else
    echo "$files_formatted"
  fi
}

cleanup_screenshot_artifacts() {
  echo "🧹 [RALPH] Cleaning up screenshots from git..."
  git rm --cached screenshots/ 2>/dev/null || true
  git checkout -- .gitignore 2>/dev/null || true
}

check_screenshots_exist() {
  [ -d "$REPO_ROOT/screenshots" ] && [ "$(ls -A "$REPO_ROOT/screenshots"/*.png 2>/dev/null)" ]
}

create_screenshot_release() {
  local temp_tag="$1"
  gh release create "$temp_tag" --repo "$REPO" --title "Screenshots for Issue #$ISSUE_NUMBER" --notes "Temporary release for screenshot storage" --target "$BRANCH_NAME" 2>&1 | tee -a /tmp/ralph-upload.log
}

upload_screenshot_to_release() {
  local temp_tag="$1"
  local screenshot_file="$2"
  local filename="$3"
  gh release upload "$temp_tag" "$screenshot_file" --repo "$REPO" --clobber 2>&1 | tee -a /tmp/ralph-upload.log && \
    gh api "repos/$REPO/releases/tags/$temp_tag" --jq ".assets[] | select(.name == \"$filename\") | .browser_download_url" 2>/dev/null
}

cleanup_old_screenshot_releases() {
  echo "🧹 [RALPH] Cleaning up old screenshot releases..."
  local seven_days_ago=$(date -d "$RALPH_SCREENSHOT_RETENTION_DAYS days ago" +%s 2>/dev/null || date -v-${RALPH_SCREENSHOT_RETENTION_DAYS}d +%s 2>/dev/null || date +%s)
  gh api "repos/$REPO/releases" --paginate --jq '.[] | select(.tag_name | startswith("screenshots-issue-")) | "\(.tag_name)|\(.id)|\(.created_at)"' 2>/dev/null | \
  while IFS='|' read -r TAG ID CREATED; do
    if [ -n "$TAG" ]; then
      local created_ts=$(date -d "$CREATED" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%SZ" "$CREATED" +%s 2>/dev/null || date +%s)
      if [ "$created_ts" -lt "$seven_days_ago" ]; then
        echo "  Deleting old release: $TAG (created $CREATED)"
        gh release delete "$TAG" --repo "$REPO" --yes 2>/dev/null || true
      fi
    fi
  done || true
}

handle_screenshots() {
  SCREENSHOT_ARGS=""
  SCREENSHOTS_EXIST=false
  
  if ! check_screenshots_exist; then
    echo "ℹ️  [RALPH] No screenshots found in screenshots/ directory"
    return
  fi
  
  echo "📸 [RALPH] Found screenshots, uploading to issue..."
  SCREENSHOTS_EXIST=true
  
  local screenshot_comment="## Screenshots (Round $REVIEW_ROUND)\n\nScreenshots captured after coding changes:\n"
  
  for screenshot_file in "$REPO_ROOT"/screenshots/*.png; do
    if [ -f "$screenshot_file" ]; then
      local filename=$(basename "$screenshot_file")
      echo "  Uploading $filename..."
      
      local temp_tag="screenshots-issue-${ISSUE_NUMBER}-round-${REVIEW_ROUND}-$(date +%s)"
      local image_url=""
      
      if create_screenshot_release "$temp_tag"; then
        image_url=$(upload_screenshot_to_release "$temp_tag" "$screenshot_file" "$filename")
      fi
      
      if [ -n "$image_url" ]; then
        screenshot_comment="$screenshot_comment\n![${filename}](${image_url})"
        echo "  ✓ Uploaded: $image_url"
      else
        screenshot_comment="$screenshot_comment\n- 📸 \`$filename\`"
        echo "  ⚠ Could not upload, will reference artifact instead"
      fi
      
      SCREENSHOT_ARGS="$SCREENSHOT_ARGS --read $screenshot_file"
    fi
  done
  
  screenshot_comment="$screenshot_comment\n\nView all screenshots in [workflow artifacts](https://github.com/$REPO/actions/runs/$GITHUB_RUN_ID) if images don't load above."
  post_comment "$screenshot_comment"
  echo "✅ [RALPH] Screenshots uploaded to issue"
  
  cleanup_old_screenshot_releases
}

execute_main_loop() {
  while [ $REVIEW_ROUND -le $MAX_REVIEW_ROUNDS ]; do
    echo "🔨 [RALPH] Coding Round $REVIEW_ROUND / $MAX_REVIEW_ROUNDS"
    
    if [ $REVIEW_ROUND -eq 1 ]; then
      PROMPT_CODING=$(build_initial_coding_prompt)
    else
      PROMPT_CODING=$(build_revision_coding_prompt)
    fi
    
    BEFORE_ROUND_SHA=$(git rev-parse HEAD)
    CODING_OUTPUT=$(run_aider_coding "$PROMPT_CODING")
    
    echo "✅ [RALPH] Coding complete for round $REVIEW_ROUND"
    echo "$CODING_OUTPUT"
    
    CODING_SUMMARY=$(get_coding_summary "$CODING_OUTPUT")
    CHANGED_FILES=$(extract_changed_files "$BEFORE_ROUND_SHA")
    CHANGED_FILES_DISPLAY=$(format_changed_files_display "$CHANGED_FILES")
    
    post_comment "## Update (Round $REVIEW_ROUND)

$CODING_SUMMARY

**Files changed:** \`$CHANGED_FILES_DISPLAY\`"
    
    cleanup_screenshot_artifacts
    

    handle_screenshots

    perform_review
    
    if review_passed; then
      # create_pull_request_and_exit will exit 0 on success,
      # or return (not exit) if tests fail
      create_pull_request_and_exit
    fi
    
    handle_review_failure
    ((REVIEW_ROUND++))
  done
}

check_for_changes() {
  local after_sha=$(git rev-parse HEAD)
  if [ "$BEFORE_ROUND_SHA" = "$after_sha" ]; then
    git add -A
    if git diff --cached --quiet; then
      echo "⚠️  [RALPH] No changes detected after coding round."
      post_comment "⚠️ **Warning**: Coding round $REVIEW_ROUND completed but no file changes were detected. Aider may have encountered an issue."
      
      if [ $REVIEW_ROUND -ge $MAX_REVIEW_ROUNDS ]; then
        post_comment "❌ **Failed**: No code changes were made after $MAX_REVIEW_ROUNDS rounds."
        exit 1
      fi
      return 1
    fi
  fi
  return 0
}

get_diff_output() {
  git --no-pager diff "$BEFORE_ROUND_SHA" HEAD 2>/dev/null || git --no-pager diff --cached
}

build_base_review_prompt() {
  local diff_output="$1"
  echo "You are a Senior Code Reviewer reviewing changes for GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

Here are the code changes:
\`\`\`diff
$diff_output
\`\`\`"
}

append_visual_verification() {
  local prompt="$1"
  if [ "$SCREENSHOTS_EXIST" = true ]; then
    echo "$prompt

Visual Verification:
Screenshots of the application have been provided to you for review. Use them to verify the visual correctness of the changes."
  else
    echo "$prompt

Visual Verification:
No visual verification was performed for this round. Review based on code changes only. Do NOT claim you verified the visual appearance."
  fi
}

append_review_instructions() {
  local prompt="$1"
  echo "$prompt

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
}

build_review_content_json() {
  local prompt_review="$1"
  jq -n --arg text "$prompt_review" '[{"type": "text", "text": $text}]'
}

attach_screenshots_to_review() {
  local review_content="$1"
  if [ "$SCREENSHOTS_EXIST" != true ]; then
    echo "$review_content"
    return
  fi
  
  for screenshot_file in "$REPO_ROOT"/screenshots/*.png; do
    if [ -f "$screenshot_file" ]; then
      local base64_img=$(base64 -w 0 "$screenshot_file" 2>/dev/null || base64 -i "$screenshot_file" 2>/dev/null)
      review_content=$(echo "$review_content" | jq --arg img "data:image/png;base64,$base64_img" '. + [{"type": "image_url", "image_url": {"url": $img}}]')
      echo "  📷 Attached screenshot: $(basename "$screenshot_file")" >&2
    fi
  done
  echo "$review_content"
}

attach_issue_images_to_review() {
  local review_content="$1"
  if [ ! -d "$ISSUE_IMAGES_DIR" ]; then
    echo "$review_content"
    return
  fi
  
  for img_file in "$ISSUE_IMAGES_DIR"/*.png; do
    if [ -f "$img_file" ]; then
      local base64_img=$(base64 -w 0 "$img_file" 2>/dev/null || base64 -i "$img_file" 2>/dev/null)
      review_content=$(echo "$review_content" | jq --arg img "data:image/png;base64,$base64_img" '. + [{"type": "image_url", "image_url": {"url": $img}}]')
      echo "  📷 Attached issue image: $(basename "$img_file")" >&2
    fi
  done
  echo "$review_content"
}

call_review_api() {
  local review_content="$1"
  local api_payload_file=$(mktemp)
  jq -n \
    --arg model "$MODEL_REVIEWER" \
    --argjson content "$review_content" \
    '{
      model: $model,
      messages: [{"role": "user", "content": $content}]
    }' > "$api_payload_file"
  
  local review_response=$(curl -s "${RALPH_OPENROUTER_API_URL:-https://openrouter.ai/api/v1/chat/completions}" \
    -H "Authorization: Bearer $OPENROUTER_API_KEY" \
    -H "Content-Type: application/json" \
    -d @"$api_payload_file")
  
  rm -f "$api_payload_file"
  echo "$review_response"
}

extract_review_content() {
  local review_response="$1"
  local review_output=$(echo "$review_response" | jq -r '.choices[0].message.content // empty')
  
  if [ -z "$review_output" ]; then
    echo "❌ [RALPH] Reviewer API returned no content. Raw response:" >&2
    echo "$review_response" | jq . 2>/dev/null || echo "$review_response" >&2
    echo "Error: Reviewer returned no response. Treating as review failure."
  else
    echo "$review_output"
  fi
}

post_review_summary() {
  local review_summary="$1"
  if [ -z "$review_summary" ]; then
    review_summary="Review completed. See full output in workflow logs."
  fi
  
  post_comment "## Review (Round $REVIEW_ROUND)

$review_summary"
}

perform_review() {
  echo "🧐 [RALPH] Starting review for round $REVIEW_ROUND..."
  
  if ! check_for_changes; then
    return
  fi
  
  DIFF_OUTPUT=$(get_diff_output)
  PROMPT_REVIEW=$(build_base_review_prompt "$DIFF_OUTPUT")
  PROMPT_REVIEW=$(append_visual_verification "$PROMPT_REVIEW")
  PROMPT_REVIEW=$(append_review_instructions "$PROMPT_REVIEW")
  
  echo "🧐 [RALPH] Calling $MODEL_REVIEWER via OpenRouter API..."
  REVIEW_CONTENT=$(build_review_content_json "$PROMPT_REVIEW")
  REVIEW_CONTENT=$(attach_screenshots_to_review "$REVIEW_CONTENT")
  REVIEW_CONTENT=$(attach_issue_images_to_review "$REVIEW_CONTENT")
  
  REVIEW_RESPONSE=$(call_review_api "$REVIEW_CONTENT")
  REVIEW_OUTPUT=$(extract_review_content "$REVIEW_RESPONSE")
  
  echo "📋 [RALPH] Review result:"
  echo "$REVIEW_OUTPUT"
  
  REVIEW_SUMMARY=$(extract_summary "$REVIEW_OUTPUT" "## Review Summary")
  post_review_summary "$REVIEW_SUMMARY"
}

review_passed() {
  [[ "$REVIEW_OUTPUT" == *"LGTM"* ]]
}

verify_all_tests_pass() {
  # Skip if no test commands configured
  if [ ${#TEST_COMMANDS[@]} -eq 0 ]; then
    echo "ℹ️  [RALPH] No tests to verify (no test commands configured)"
    return 0
  fi
  
  echo "🧪 [RALPH] Running all tests to verify..."
  
  local all_passed=true
  local failure_output=""
  
  for test_cmd in "${TEST_COMMANDS[@]}"; do
    echo "  Running: $test_cmd"
    if output=$(eval "$test_cmd" 2>&1); then
      echo "    ✅ Passed"
    else
      echo "    ❌ Failed"
      all_passed=false
      failure_output="$failure_output\n\n### Test Command: \`$test_cmd\`\n\n\`\`\`\n$output\n\`\`\`"
    fi
  done
  
  if [ "$all_passed" = false ]; then
    TESTS_FAILED_OUTPUT="$failure_output"
    return 1
  fi
  
  echo "✅ [RALPH] All tests passed!"
  return 0
}

commit_if_needed() {
  local final_sha=$(git rev-parse HEAD)
  if [ "$INITIAL_SHA" = "$final_sha" ]; then
    git add -A
    if ! git diff --cached --quiet; then
      echo "📝 [RALPH] Committing uncommitted changes..."
      git commit -m "Fix: Automated resolution for Issue #$ISSUE_NUMBER"
    fi
  fi
}

create_pr() {
  local test_status=""
  if [ ${#TEST_COMMANDS[@]} -gt 0 ]; then
    test_status="\n\n## Test Results\n✅ All ${#TEST_COMMANDS[@]} test command(s) passed"
  fi
  
  local pr_body="Closes #$ISSUE_NUMBER

This PR was automatically generated by Ralph, the autonomous coding agent.

## Changes Made
$CODING_SUMMARY

## Review Status
✅ Code review passed$test_status

## Screenshots
See issue comments for visual verification screenshots, or download from [workflow artifacts](https://github.com/$REPO/actions/runs/$GITHUB_RUN_ID)"
  
  gh pr create \
    --repo "$REPO" \
    --base "$RALPH_PR_BASE_BRANCH" \
    --head "$BRANCH_NAME" \
    --title "Fix: Issue #$ISSUE_NUMBER (Ralph Agent)" \
    --body "$pr_body"
}

create_pull_request_and_exit() {
  echo "✅ [RALPH] Review passed!"
  
  # Verify all tests pass before creating PR
  if ! verify_all_tests_pass; then
    echo "❌ [RALPH] Tests failed! Returning to coding loop..."
    post_comment "❌ **Tests Failed After Code Review**

The code review passed, but the following tests are still failing:
$TESTS_FAILED_OUTPUT

Returning to coding phase to fix these test failures."
    
    # Set reviewer feedback to test failures and continue loop
    REVIEWER_FEEDBACK="Tests are failing. You must fix these test failures:\n$TESTS_FAILED_OUTPUT"
    return
  fi
  
  echo "🚀 [RALPH] Creating PR..."
  
  commit_if_needed
  git push origin "$BRANCH_NAME"
  create_pr
  
  post_comment "✅ **Success!** Ralph has completed the work and created a PR.

Review passed after $REVIEW_ROUND round(s)."
  
  echo "🎉 [RALPH] PR Created successfully."
  exit 0
}

handle_no_changes_failure() {
  echo "⚠️  [RALPH] No changes to commit."
  
  local failure_msg="❌ **Failed** after $MAX_REVIEW_ROUNDS review rounds.

## Last Review Issues
$REVIEW_SUMMARY

## What to do
No code changes were made. The agent may have encountered issues or the problem may require a different approach.

You can:
1. Add the \`ralph-retry\` label to try again
2. Manually implement the changes
3. Close this issue if it's no longer needed"
  
  post_comment "$failure_msg"
  exit 1
}

handle_wip_failure() {
  git push origin "$BRANCH_NAME"
  
  local failure_msg="❌ **Failed** after $MAX_REVIEW_ROUNDS review rounds.

## Last Review Issues
$REVIEW_SUMMARY

## What to do
The work-in-progress has been pushed to branch \`$BRANCH_NAME\`.

You can:
1. Review the changes manually and fix the remaining issues
2. Add the \`ralph-retry\` label to try again
3. Close this issue if it's no longer needed"
  
  post_comment "$failure_msg"
  exit 1
}

handle_review_failure() {
  REVIEWER_FEEDBACK="$REVIEW_OUTPUT"
  
  if [ $REVIEW_ROUND -ge $MAX_REVIEW_ROUNDS ]; then
    echo "❌ [RALPH] Failed after $MAX_REVIEW_ROUNDS review rounds."
    
    local final_sha=$(git rev-parse HEAD)
    if [ "$INITIAL_SHA" = "$final_sha" ]; then
      git add -A
      if git diff --cached --quiet; then
        handle_no_changes_failure
      else
        git commit -m "WIP: Issue #$ISSUE_NUMBER (failed after $MAX_REVIEW_ROUNDS rounds)"
      fi
    fi
    
    handle_wip_failure
  fi
  
  echo "🔄 [RALPH] Review failed. Starting round $((REVIEW_ROUND + 1))..."
}

main() {
  validate_environment
  initialize_configuration
  navigate_to_repo_root
  preprocess_issue_details
  resolve_test_commands
  apply_difficulty_overrides
  build_issue_image_flags
  configure_git_user
  create_feature_branch
  initialize_loop_state
  run_test_scaffolding
  execute_main_loop
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main
fi

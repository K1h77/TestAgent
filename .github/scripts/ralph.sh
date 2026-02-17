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
  if [ -z "$OPENROUTER_API_KEY" ]; then
    echo "❌ Error: OPENROUTER_API_KEY env var missing. Required for aider API calls."
    exit 1
  fi
  
  # Validate gh CLI is available and authenticated
  if ! command -v gh &>/dev/null; then
    echo "❌ Error: GitHub CLI (gh) is not installed or not in PATH."
    exit 1
  fi
  if ! gh auth status &>/dev/null; then
    echo "❌ Error: GitHub CLI is not authenticated. Run 'gh auth login' first."
    exit 1
  fi
  
  # Validate aider is available
  if ! command -v aider &>/dev/null; then
    echo "❌ Error: aider is not installed or not in PATH."
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
  
  # Validate required configuration
  local missing=()
  [ -z "$MODEL_ARCHITECT" ] && missing+=("RALPH_MODEL_ARCHITECT")
  [ -z "$MODEL_CODER" ] && missing+=("RALPH_MODEL_CODER")
  [ -z "$MODEL_REVIEWER" ] && missing+=("RALPH_MODEL_REVIEWER")
  [ -z "$MAX_REVIEW_ROUNDS" ] && missing+=("RALPH_MAX_REVIEW_ROUNDS")
  
  if [ ${#missing[@]} -gt 0 ]; then
    echo "❌ [RALPH] Missing required configuration: ${missing[*]}"
    echo "   Check .github/configure-ralph for missing values."
    exit 1
  fi
  
  if ! [[ "$MAX_REVIEW_ROUNDS" =~ ^[0-9]+$ ]] || [ "$MAX_REVIEW_ROUNDS" -lt 1 ]; then
    echo "❌ [RALPH] RALPH_MAX_REVIEW_ROUNDS must be a positive integer, got: '$MAX_REVIEW_ROUNDS'"
    exit 1
  fi
  
  echo "🤖 [RALPH] Waking up. Target: Issue #$ISSUE_NUMBER in $REPO"
}

navigate_to_repo_root() {
  local toplevel
  toplevel=$(git rev-parse --show-toplevel 2>&1) || {
    echo "❌ [RALPH] Not inside a git repository. Cannot determine repo root."
    echo "   git output: $toplevel"
    exit 1
  }
  cd "$toplevel"
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
  
  # Validate that ISSUE_DETAILS was actually populated
  if [ -z "$ISSUE_DETAILS" ]; then
    echo "❌ [RALPH] ISSUE_DETAILS is empty after preprocessing. The issue content could not be fetched."
    echo "   This means aider will receive no context and will hallucinate a task."
    post_comment "❌ **Fatal**: Could not fetch issue details for #$ISSUE_NUMBER. Ralph cannot proceed without knowing what to do." 2>/dev/null || true
    exit 1
  fi
  
  if [ -z "$ISSUE_TITLE" ]; then
    echo "❌ [RALPH] ISSUE_TITLE is empty. Cannot proceed without an issue title."
    exit 1
  fi
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
  
  if [ -z "$RALPH_BOT_EMAIL" ] || [ -z "$RALPH_BOT_NAME" ]; then
    echo "❌ [RALPH] RALPH_BOT_EMAIL and RALPH_BOT_NAME must be set for git commits."
    exit 1
  fi
  
  git config --global user.email "$RALPH_BOT_EMAIL"
  git config --global user.name "$RALPH_BOT_NAME"
}

create_feature_branch() {
  BRANCH_NAME="$RALPH_BRANCH_PREFIX-$ISSUE_NUMBER-auto-$(date +%s)"
  
  if [ -z "$RALPH_BRANCH_PREFIX" ]; then
    echo "❌ [RALPH] RALPH_BRANCH_PREFIX is empty. Cannot create branch."
    exit 1
  fi
  
  if ! git checkout -b "$BRANCH_NAME" 2>&1; then
    echo "❌ [RALPH] Failed to create branch: $BRANCH_NAME"
    exit 1
  fi
  echo "✅ [RALPH] Created branch: $BRANCH_NAME"
}

initialize_loop_state() {
  REVIEW_ROUND=1
  REVIEWER_FEEDBACK=""
  INITIAL_SHA=$(git rev-parse HEAD)
  SCREENSHOT_URLS=()
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
  local test_prompt_file=$(mktemp)
  echo "$test_prompt" > "$test_prompt_file"
  eval "aider --yes-always --no-check-update --architect --model \"$MODEL_ARCHITECT\" --editor-model \"$MODEL_CODER\" $ISSUE_IMAGE_FLAGS --message-file \"$test_prompt_file\""
  rm -f "$test_prompt_file"
  
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
  local prompt_file=$(mktemp)
  echo "$prompt" > "$prompt_file"
  
  local aider_exit_code=0
  eval "aider --yes-always --no-check-update --architect --model \"$MODEL_ARCHITECT\" --editor-model \"$MODEL_CODER\" $ISSUE_IMAGE_FLAGS $AIDER_TEST_FLAGS --message-file \"$prompt_file\"" || aider_exit_code=$?
  
  rm -f "$prompt_file"
  
  if [ $aider_exit_code -ne 0 ]; then
    echo "⚠️  [RALPH] Aider exited with code $aider_exit_code. It may have encountered an error."
  fi
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
  SCREENSHOT_URLS=()
  
  if ! check_screenshots_exist; then
    echo "ℹ️  [RALPH] No screenshots found in screenshots/ directory"
    return
  fi
  
  echo "📸 [RALPH] Found screenshots, uploading for PR..."
  SCREENSHOTS_EXIST=true
  
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
        SCREENSHOT_URLS+=("$filename|$image_url")
        echo "  ✓ Uploaded: $image_url"
      else
        SCREENSHOT_URLS+=("$filename|")
        echo "  ⚠ Could not upload"
      fi
      
      SCREENSHOT_ARGS="$SCREENSHOT_ARGS --read $screenshot_file"
    fi
  done
  
  echo "✅ [RALPH] Screenshots uploaded (${#SCREENSHOT_URLS[@]} files)"
  
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
    
    # Sanity check: prompt must contain issue details
    if [ -z "$PROMPT_CODING" ]; then
      echo "❌ [RALPH] Coding prompt is empty. Cannot proceed."
      post_comment "❌ **Fatal**: Failed to build coding prompt for round $REVIEW_ROUND."
      exit 1
    fi
    
    BEFORE_ROUND_SHA=$(git rev-parse HEAD)
    CODING_OUTPUT=$(run_aider_coding "$PROMPT_CODING")
    
    if [ -z "$CODING_OUTPUT" ]; then
      echo "⚠️  [RALPH] Aider produced no output for round $REVIEW_ROUND."
    fi
    
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
  local diff
  diff=$(git --no-pager diff "$BEFORE_ROUND_SHA" HEAD 2>/dev/null || git --no-pager diff --cached 2>/dev/null)
  
  if [ -z "$diff" ]; then
    echo "❌ [RALPH] Diff output is empty despite changes being detected." >&2
  fi
  
  echo "$diff"
}

build_review_prompt() {
  local diff_output="$1"

  local visual_section
  if [ "$SCREENSHOTS_EXIST" = true ]; then
    visual_section="Visual Verification:
Screenshots of the application have been provided to you for review. Use them to verify the visual correctness of the changes."
  else
    visual_section="Visual Verification:
No visual verification was performed for this round. Review based on code changes only. Do NOT claim you verified the visual appearance."
  fi

  echo "You are a Senior Code Reviewer reviewing changes for GitHub Issue #$ISSUE_NUMBER in repository $REPO.

Here are the issue details:
$ISSUE_DETAILS

If there are images attached to this issue, they have been provided to you. Use them to understand the visual requirements.

Here are the code changes:
\`\`\`diff
$diff_output
\`\`\`

IMPORTANT CONTEXT: You have access to the full codebase via the repo map. Use it to verify:
- Whether the changes are complete (all relevant files modified)
- Whether hover states, focus states, and other interactive elements are also updated
- Whether the changes are consistent with the rest of the codebase

$visual_section

Your task:
1. Review the changes against the issue requirements.
2. Use the repo map to check for completeness — are ALL relevant files updated?
3. Check for bugs, security issues, code quality problems, and missing functionality.
4. For UI/styling issues, consider whether visual verification is needed and available.
5. If the code is good and fully addresses the issue (including visual correctness if applicable), output EXACTLY on its own line: 'LGTM'
6. If there are issues, output a detailed numbered list of problems that MUST be fixed.

End your response with a section that starts with the line '## Review Summary' (on its own line). In this section:
- If LGTM: Write 2-3 sentences explaining why it looks good
- If issues found: Write 3-5 bullet points maximum, each clearly stating the problem

Be thorough but fair. Make sure to include the '## Review Summary' section at the end of your response."
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
  if [ -z "$DIFF_OUTPUT" ]; then
    echo "❌ [RALPH] Cannot perform review: diff output is empty."
    REVIEW_OUTPUT="REVIEW_FAILED: No diff content available to review."
    post_comment "⚠️ **Review Skipped (Round $REVIEW_ROUND)**: Could not generate a diff of the changes."
    return
  fi
  
  # Build review prompt and write to temp file (avoids shell interpretation of special chars)
  local review_prompt_file=$(mktemp)
  build_review_prompt "$DIFF_OUTPUT" > "$review_prompt_file"
  
  # Build read flags for screenshots (reviewer sees but does not edit)
  local review_read_flags=""
  if [ "$SCREENSHOTS_EXIST" = true ]; then
    for screenshot_file in "$REPO_ROOT"/screenshots/*.png; do
      if [ -f "$screenshot_file" ]; then
        review_read_flags="$review_read_flags --read \"$screenshot_file\""
      fi
    done
  fi
  
  echo "🧐 [RALPH] Reviewing with $MODEL_REVIEWER via aider (codebase-aware)..."
  
  local review_exit_code=0
  REVIEW_OUTPUT=$(eval "aider --yes-always --no-check-update --chat-mode ask --model \"$MODEL_REVIEWER\" $ISSUE_IMAGE_FLAGS $review_read_flags --message-file \"$review_prompt_file\"") || review_exit_code=$?
  
  rm -f "$review_prompt_file"
  
  if [ $review_exit_code -ne 0 ]; then
    echo "⚠️  [RALPH] Reviewer exited with code $review_exit_code."
  fi
  
  if [ -z "$REVIEW_OUTPUT" ]; then
    echo "❌ [RALPH] Reviewer produced no output."
    REVIEW_OUTPUT="REVIEW_FAILED: Reviewer returned no content. This is not an approval."
    post_comment "❌ **Review Failed (Round $REVIEW_ROUND)**: Reviewer produced no output."
    return
  fi
  
  echo "📋 [RALPH] Review result:"
  echo "$REVIEW_OUTPUT"
  
  REVIEW_SUMMARY=$(extract_summary "$REVIEW_OUTPUT" "## Review Summary")
  post_review_summary "$REVIEW_SUMMARY"
}

review_passed() {
  # Check for standalone LGTM (not embedded in phrases like "Cannot provide LGTM")
  echo "$REVIEW_OUTPUT" | grep -qP '^\s*LGTM\s*$'
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
  
  local screenshots_section=""
  if [ ${#SCREENSHOT_URLS[@]} -gt 0 ]; then
    screenshots_section="\n\n## Screenshots\n\nVisual verification screenshots from the final successful round:\n"
    for entry in "${SCREENSHOT_URLS[@]}"; do
      local filename="${entry%%|*}"
      local url="${entry#*|}"
      if [ -n "$url" ]; then
        screenshots_section="${screenshots_section}\n![${filename}](${url})"
      else
        screenshots_section="${screenshots_section}\n- 📸 \`$filename\` (upload failed)"
      fi
    done
  fi
  
  local pr_body="Closes #$ISSUE_NUMBER

This PR was automatically generated by Ralph, the autonomous coding agent.

## Changes Made
$CODING_SUMMARY

## Review Status
✅ Code review passed$test_status$screenshots_section"
  
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
  
  if ! git push origin "$BRANCH_NAME" 2>&1; then
    echo "❌ [RALPH] Failed to push branch $BRANCH_NAME to origin."
    post_comment "❌ **Error**: Failed to push branch \`$BRANCH_NAME\` to origin. Check repository permissions."
    exit 1
  fi
  
  if ! create_pr; then
    echo "❌ [RALPH] Failed to create pull request."
    post_comment "❌ **Error**: Branch was pushed but PR creation failed. You can manually create a PR from branch \`$BRANCH_NAME\`."
    exit 1
  fi
  
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
  
  # Guard: if review output is empty or an internal failure marker, set useful feedback
  if [ -z "$REVIEWER_FEEDBACK" ] || [[ "$REVIEWER_FEEDBACK" == REVIEW_FAILED:* ]] || [[ "$REVIEWER_FEEDBACK" == REVIEW_API_FAILURE:* ]]; then
    REVIEWER_FEEDBACK="The review could not be completed (API failure or empty response). Please re-examine the issue requirements carefully and ensure your implementation is complete and correct. Re-read the issue details and verify every requirement is addressed."
  fi
  
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

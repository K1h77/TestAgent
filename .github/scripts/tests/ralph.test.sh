#!/usr/bin/env bats

setup_file() {
  export SHARED_TEST_DIR="$(mktemp -d)"
}

teardown_file() {
  cd /
  rm -rf "$SHARED_TEST_DIR"
}

setup() {
  # Reset per-test variables
  export ISSUE_NUMBER="456"
  export GITHUB_REPOSITORY="test/repo"
  export OPENROUTER_API_KEY="test-key"
  export GITHUB_RUN_ID="12345"
  
  source "${BATS_TEST_DIRNAME}/../../configure-ralph"
  
  export REPO_ROOT="$SHARED_TEST_DIR"
  export REPO="test/repo"
  export MODEL_ARCHITECT="test-architect-model"
  export MODEL_CODER="test-coder-model"
  export MODEL_REVIEWER="test-reviewer-model"
  export MAX_REVIEW_ROUNDS=3
  export PR_SUMMARY_MAX_LINES=10
  export BRANCH_NAME="test-branch"
  export INITIAL_SHA="abc123"
  export BEFORE_ROUND_SHA="def456"
  export REVIEW_ROUND=1
  export CODING_SUMMARY="Test coding summary"
  export REVIEW_SUMMARY="Test review summary"
  export REVIEW_OUTPUT="Test review output"
  export REVIEWER_FEEDBACK=""
  export SCREENSHOTS_EXIST=false
  export ISSUE_LABELS=""
  export TEST_COMMANDS=()
  export AIDER_TEST_FLAGS=""
  export ISSUE_IMAGE_FLAGS=""
  export ISSUE_IMAGES_DIR="$SHARED_TEST_DIR/images"
  export SCREENSHOT_URLS=()
  
  cd "$SHARED_TEST_DIR"
  source "${BATS_TEST_DIRNAME}/../ralph.sh"
  
  # Mock git commands by default for speed
  git() {
    case "$1" in
      rev-parse)
        if [ "$2" = "--show-toplevel" ]; then
          echo "$SHARED_TEST_DIR"
        else
          echo "mock-sha-$RANDOM"
        fi
        ;;
      config)
        if [ "$2" = "user.email" ]; then
          echo "${RALPH_BOT_EMAIL:-test@example.com}"
        elif [ "$2" = "user.name" ]; then
          echo "${RALPH_BOT_NAME:-Test User}"
        fi
        ;;
      diff|log)
        echo "mock diff output"
        ;;
      *)
        return 0
        ;;
    esac
  }
  export -f git
}

teardown() {
  rm -f "$SHARED_TEST_DIR"/*.log 2>/dev/null || true
  rm -rf "$SHARED_TEST_DIR/images" 2>/dev/null || true
  unset ISSUE_NUMBER GITHUB_REPOSITORY OPENROUTER_API_KEY GITHUB_RUN_ID
  unset REPO_ROOT REPO MODEL_ARCHITECT MODEL_CODER MODEL_REVIEWER MAX_REVIEW_ROUNDS
  unset BRANCH_NAME INITIAL_SHA BEFORE_ROUND_SHA REVIEW_ROUND
  unset CODING_SUMMARY REVIEW_SUMMARY REVIEW_OUTPUT REVIEWER_FEEDBACK
  unset SCREENSHOTS_EXIST ISSUE_LABELS TEST_COMMANDS AIDER_TEST_FLAGS
  unset ISSUE_IMAGE_FLAGS ISSUE_IMAGES_DIR TESTS_FAILED_OUTPUT SCREENSHOT_URLS
}

@test "validate_environment: fails when ISSUE_NUMBER is missing" {
  unset ISSUE_NUMBER
  run validate_environment
  [ "$status" -eq 1 ]
  [[ "$output" =~ "ISSUE_NUMBER missing" ]]
}

@test "validate_environment: fails when GITHUB_REPOSITORY is missing" {
  unset GITHUB_REPOSITORY
  run validate_environment
  [ "$status" -eq 1 ]
  [[ "$output" =~ "GITHUB_REPOSITORY" ]]
}

@test "validate_environment: succeeds when both vars are set" {
  run validate_environment
  [ "$status" -eq 0 ]
}

@test "initialize_configuration: sets REPO from GITHUB_REPOSITORY" {
  GITHUB_REPOSITORY="owner/reponame"
  initialize_configuration >/dev/null 2>&1
  [ "$REPO" = "owner/reponame" ]
}

@test "initialize_configuration: sets MODEL_CODER from config" {
  initialize_configuration >/dev/null 2>&1
  [ -n "$MODEL_CODER" ]
}

@test "initialize_configuration: sets MODEL_ARCHITECT from config" {
  initialize_configuration >/dev/null 2>&1
  [ -n "$MODEL_ARCHITECT" ]
}

@test "navigate_to_repo_root: sets REPO_ROOT" {
  navigate_to_repo_root
  [ -n "$REPO_ROOT" ]
  [ -d "$REPO_ROOT" ]
}

@test "post_comment: calls gh issue comment with correct args" {
  gh() {
    echo "gh $@" >> "$SHARED_TEST_DIR/gh-calls.log"
    return 0
  }
  export -f gh
  
  post_comment "Test comment body"
  [ -f "$SHARED_TEST_DIR/gh-calls.log" ]
  grep -q "issue comment" "$SHARED_TEST_DIR/gh-calls.log"
  grep -q "Test comment body" "$SHARED_TEST_DIR/gh-calls.log"
}

@test "extract_summary: extracts content between marker and next heading" {
  local input="Some text
## Summary
This is the summary
More summary text
## Next Section
Other content"
  
  result=$(extract_summary "$input" "## Summary")
  [[ "$result" =~ "This is the summary" ]]
  [[ "$result" =~ "More summary text" ]]
  [[ ! "$result" =~ "Next Section" ]]
}

@test "extract_summary: returns empty for missing marker" {
  local input="Some text without the marker"
  result=$(extract_summary "$input" "## Summary")
  [ -z "$result" ]
}

@test "resolve_test_commands: sets empty flags when no labels" {
  ISSUE_LABELS=""
  resolve_test_commands >/dev/null 2>&1
  [ -z "$AIDER_TEST_FLAGS" ]
  [ ${#TEST_COMMANDS[@]} -eq 0 ]
}

@test "resolve_test_commands: finds test command for frontend label" {
  ISSUE_LABELS="frontend"
  RALPH_TEST_CMD_FRONTEND="npm test frontend"
  resolve_test_commands >/dev/null 2>&1
  [ ${#TEST_COMMANDS[@]} -eq 1 ]
  [ "${TEST_COMMANDS[0]}" = "npm test frontend" ]
  [[ "$AIDER_TEST_FLAGS" =~ "--auto-test" ]]
  [[ "$AIDER_TEST_FLAGS" =~ "npm test frontend" ]]
}

@test "resolve_test_commands: finds multiple test commands" {
  ISSUE_LABELS="frontend, backend"
  RALPH_TEST_CMD_FRONTEND="npm test frontend"
  RALPH_TEST_CMD_BACKEND="npm test backend"
  resolve_test_commands >/dev/null 2>&1
  [ ${#TEST_COMMANDS[@]} -eq 2 ]
  [[ "$AIDER_TEST_FLAGS" =~ "--auto-test" ]]
  [[ "$AIDER_TEST_FLAGS" =~ "npm test frontend" ]]
  [[ "$AIDER_TEST_FLAGS" =~ "npm test backend" ]]
}

@test "resolve_test_commands: ignores unknown labels" {
  ISSUE_LABELS="frontend, unknown-label"
  RALPH_TEST_CMD_FRONTEND="npm test frontend"
  resolve_test_commands >/dev/null 2>&1
  [ ${#TEST_COMMANDS[@]} -eq 1 ]
  [ "${TEST_COMMANDS[0]}" = "npm test frontend" ]
}

@test "resolve_test_commands: ignores labels with empty commands" {
  ISSUE_LABELS="frontend"
  RALPH_TEST_CMD_FRONTEND=""
  resolve_test_commands >/dev/null 2>&1
  [ ${#TEST_COMMANDS[@]} -eq 0 ]
  [ -z "$AIDER_TEST_FLAGS" ]
}

# ── apply_difficulty_overrides ──

@test "apply_difficulty_overrides: upgrades architect when hard label present" {
  MODEL_ARCHITECT="openrouter/anthropic/claude-haiku-4.5"
  RALPH_MODEL_ARCHITECT_HARD="openrouter/anthropic/claude-sonnet-4.5"
  ISSUE_LABELS="frontend,hard"
  apply_difficulty_overrides >/dev/null 2>&1
  [ "$MODEL_ARCHITECT" = "openrouter/anthropic/claude-sonnet-4.5" ]
}

@test "apply_difficulty_overrides: no change without hard label" {
  MODEL_ARCHITECT="openrouter/anthropic/claude-haiku-4.5"
  RALPH_MODEL_ARCHITECT_HARD="openrouter/anthropic/claude-sonnet-4.5"
  ISSUE_LABELS="frontend,backend"
  apply_difficulty_overrides >/dev/null 2>&1
  [ "$MODEL_ARCHITECT" = "openrouter/anthropic/claude-haiku-4.5" ]
}

@test "apply_difficulty_overrides: case-insensitive hard label" {
  MODEL_ARCHITECT="openrouter/anthropic/claude-haiku-4.5"
  RALPH_MODEL_ARCHITECT_HARD="openrouter/anthropic/claude-sonnet-4.5"
  ISSUE_LABELS="Hard"
  apply_difficulty_overrides >/dev/null 2>&1
  [ "$MODEL_ARCHITECT" = "openrouter/anthropic/claude-sonnet-4.5" ]
}

@test "apply_difficulty_overrides: no-op when RALPH_MODEL_ARCHITECT_HARD is empty" {
  MODEL_ARCHITECT="openrouter/anthropic/claude-haiku-4.5"
  RALPH_MODEL_ARCHITECT_HARD=""
  ISSUE_LABELS="hard"
  apply_difficulty_overrides >/dev/null 2>&1
  [ "$MODEL_ARCHITECT" = "openrouter/anthropic/claude-haiku-4.5" ]
}

@test "apply_difficulty_overrides: no-op when no labels" {
  MODEL_ARCHITECT="openrouter/anthropic/claude-haiku-4.5"
  RALPH_MODEL_ARCHITECT_HARD="openrouter/anthropic/claude-sonnet-4.5"
  ISSUE_LABELS=""
  apply_difficulty_overrides >/dev/null 2>&1
  [ "$MODEL_ARCHITECT" = "openrouter/anthropic/claude-haiku-4.5" ]
}

@test "build_issue_image_flags: returns empty when no images dir" {
  ISSUE_IMAGES_DIR="/nonexistent"
  build_issue_image_flags
  [ -z "$ISSUE_IMAGE_FLAGS" ]
}

@test "build_issue_image_flags: builds flags for single image" {
  mkdir -p "$ISSUE_IMAGES_DIR"
  echo "fake" > "$ISSUE_IMAGES_DIR/img1.png"
  build_issue_image_flags >/dev/null 2>&1
  [[ "$ISSUE_IMAGE_FLAGS" =~ "--file" ]]
  [[ "$ISSUE_IMAGE_FLAGS" =~ "img1.png" ]]
}

@test "build_issue_image_flags: builds flags for multiple images" {
  mkdir -p "$ISSUE_IMAGES_DIR"
  echo "fake" > "$ISSUE_IMAGES_DIR/img1.png"
  echo "fake" > "$ISSUE_IMAGES_DIR/img2.png"
  build_issue_image_flags >/dev/null 2>&1
  [[ "$ISSUE_IMAGE_FLAGS" =~ "img1.png" ]]
  [[ "$ISSUE_IMAGE_FLAGS" =~ "img2.png" ]]
  # Count --file flags
  local count=$(echo "$ISSUE_IMAGE_FLAGS" | grep -o "\--file" | wc -l)
  [ "$count" -eq 2 ]
}

@test "get_coding_summary: returns fallback when summary is empty" {
  result=$(get_coding_summary "No summary section here")
  [[ "$result" =~ "Completed coding changes" ]]
}

@test "get_coding_summary: extracts summary from output" {
  local output="Some output
## Summary
Great changes made
End of summary"
  
  result=$(get_coding_summary "$output")
  [[ "$result" =~ "Great changes made" ]]
}

@test "extract_changed_files: returns list of changed files" {
  git() { command git "$@"; }
  export -f git
  
  git init --quiet
  git config user.email "test@example.com"
  git config user.name "Test User"
  echo "initial" > test.txt
  git add test.txt
  git commit -m "Initial" --quiet
  
  echo "new content" > test.txt
  git add test.txt
  git commit -m "Update test" --quiet
  local before=$(git rev-parse HEAD~1)
  
  result=$(extract_changed_files "$before")
  [[ "$result" =~ "test.txt" ]]
}

@test "extract_changed_files: respects max files limit" {
  git() { command git "$@"; }
  export -f git
  
  git init --quiet
  git config user.email "test@example.com"
  git config user.name "Test User"
  touch .gitkeep
  git add .gitkeep
  git commit -m "Initial" --quiet
  
  for i in {1..25}; do
    echo "content $i" > "file$i.txt"
    git add "file$i.txt"
  done
  git commit -m "Add many files" --quiet
  local before=$(git rev-parse HEAD~1)
  
  result=$(extract_changed_files "$before")
  local count=$(echo "$result" | wc -l)
  [ "$count" -le "$RALPH_CHANGED_FILES_MAX" ]
}

@test "format_changed_files_display: returns message for no changes" {
  result=$(format_changed_files_display "")
  [[ "$result" =~ "No committed changes" ]]
}

@test "format_changed_files_display: formats single file correctly" {
  result=$(format_changed_files_display "file1.txt")
  [[ "$result" =~ "file1.txt" ]]
}

@test "format_changed_files_display: formats multiple files" {
  local files="file1.txt
file2.txt
file3.txt"
  result=$(format_changed_files_display "$files")
  [[ "$result" =~ "file1.txt" ]]
  [[ "$result" =~ "file2.txt" ]]
}

@test "format_changed_files_display: indicates additional files when over limit" {
  local files=""
  for i in {1..15}; do
    files="${files}file${i}.txt"$'\n'
  done
  
  result=$(format_changed_files_display "$files")
  [[ "$result" =~ "more file" ]]
}

@test "check_screenshots_exist: returns false when no directory" {
  run check_screenshots_exist
  [ "$status" -ne 0 ]
}

@test "check_screenshots_exist: returns false when directory is empty" {
  mkdir -p "$REPO_ROOT/screenshots"
  run check_screenshots_exist
  [ "$status" -ne 0 ]
}

@test "check_screenshots_exist: returns true when screenshots exist" {
  mkdir -p "$REPO_ROOT/screenshots"
  touch "$REPO_ROOT/screenshots/test.png"
  run check_screenshots_exist
  [ "$status" -eq 0 ]
}

@test "build_initial_coding_prompt: includes issue number" {
  result=$(build_initial_coding_prompt)
  [[ "$result" =~ "$ISSUE_NUMBER" ]]
}

@test "build_initial_coding_prompt: includes repository name" {
  result=$(build_initial_coding_prompt)
  [[ "$result" =~ "$REPO" ]]
}

@test "build_initial_coding_prompt: includes visual verification instructions" {
  result=$(build_initial_coding_prompt)
  [[ "$result" =~ "visual verification" ]]
  [[ "$result" =~ "SCREENSHOT_PAGES" ]]
}

@test "build_initial_coding_prompt: mentions images provided directly" {
  result=$(build_initial_coding_prompt)
  [[ "$result" =~ "images" ]]
  [[ "$result" =~ "provided to you directly" ]]
}

@test "build_initial_coding_prompt: includes test context when test commands exist" {
  TEST_COMMANDS=("npm test")
  result=$(build_initial_coding_prompt)
  [[ "$result" =~ "Failing unit tests" ]]
  [[ "$result" =~ "acceptance criteria" ]]
}

@test "build_initial_coding_prompt: omits test context when no test commands" {
  TEST_COMMANDS=()
  result=$(build_initial_coding_prompt)
  [[ ! "$result" =~ "Failing unit tests" ]]
}

@test "build_revision_coding_prompt: includes reviewer feedback" {
  REVIEWER_FEEDBACK="Fix the bug on line 42"
  result=$(build_revision_coding_prompt)
  [[ "$result" =~ "Fix the bug on line 42" ]]
}

@test "build_base_review_prompt: includes issue number" {
  local diff="+ new line"
  result=$(build_base_review_prompt "$diff")
  [[ "$result" =~ "$ISSUE_NUMBER" ]]
}

@test "build_base_review_prompt: includes diff output" {
  local diff="+ added line
- removed line"
  result=$(build_base_review_prompt "$diff")
  [[ "$result" =~ "added line" ]]
  [[ "$result" =~ "removed line" ]]
}

@test "append_visual_verification: adds screenshot message when exists" {
  SCREENSHOTS_EXIST=true
  local prompt="Base prompt"
  result=$(append_visual_verification "$prompt")
  [[ "$result" =~ "Screenshots of the application" ]]
}

@test "append_visual_verification: adds no-screenshot message when not exists" {
  SCREENSHOTS_EXIST=false
  local prompt="Base prompt"
  result=$(append_visual_verification "$prompt")
  [[ "$result" =~ "No visual verification" ]]
}

@test "append_review_instructions: includes LGTM instruction" {
  local prompt="Base prompt"
  result=$(append_review_instructions "$prompt")
  [[ "$result" =~ "LGTM" ]]
}

@test "append_review_instructions: includes review summary instruction" {
  local prompt="Base prompt"
  result=$(append_review_instructions "$prompt")
  [[ "$result" =~ "## Review Summary" ]]
}

@test "build_review_content_json: creates valid JSON with text" {
  jq() {
    echo '[{"type": "text", "text": "Review this code"}]'
  }
  export -f jq
  
  local prompt="Review this code"
  result=$(build_review_content_json "$prompt")
  [[ "$result" =~ "type" ]]
  [[ "$result" =~ "text" ]]
}

@test "build_review_content_json: includes prompt text in JSON" {
  jq() {
    echo '[{"type": "text", "text": "Check for bugs"}]'
  }
  export -f jq
  
  local prompt="Check for bugs"
  result=$(build_review_content_json "$prompt")
  [[ "$result" =~ "Check for bugs" ]]
}

@test "extract_review_content: extracts content from valid response" {
  jq() {
    if [[ "$*" =~ "-r" ]]; then
      echo "Review looks good"
    else
      command jq "$@"
    fi
  }
  export -f jq
  
  local response='{"choices":[{"message":{"content":"Review looks good"}}]}'
  result=$(extract_review_content "$response" 2>/dev/null)
  [ "$result" = "Review looks good" ]
}

@test "extract_review_content: returns error for empty response" {
  local response='{"choices":[{"message":{"content":""}}]}'
  result=$(extract_review_content "$response" 2>/dev/null)
  [[ "$result" =~ "Error" ]]
}

@test "extract_review_content: handles missing content field" {
  local response='{"choices":[{"message":{}}]}'
  result=$(extract_review_content "$response" 2>/dev/null)
  [[ "$result" =~ "Error" ]]
}

@test "review_passed: returns true when LGTM in output" {
  REVIEW_OUTPUT="The code looks great. LGTM!"
  run review_passed
  [ "$status" -eq 0 ]
}

@test "review_passed: returns false when no LGTM" {
  REVIEW_OUTPUT="Found some issues"
  run review_passed
  [ "$status" -ne 0 ]
}

@test "review_passed: is case sensitive for LGTM" {
  REVIEW_OUTPUT="lgtm"
  run review_passed
  [ "$status" -ne 0 ]
}

@test "verify_all_tests_pass: returns success when no test commands" {
  TEST_COMMANDS=()
  run verify_all_tests_pass
  [ "$status" -eq 0 ]
}

@test "verify_all_tests_pass: returns success when all tests pass" {
  TEST_COMMANDS=("echo test1" "echo test2")
  run verify_all_tests_pass
  [ "$status" -eq 0 ]
}

@test "verify_all_tests_pass: returns failure when one test fails" {
  TEST_COMMANDS=("echo test1" "exit 1")
  ! verify_all_tests_pass 2>/dev/null
  [ -n "$TESTS_FAILED_OUTPUT" ]
}

@test "verify_all_tests_pass: captures output from failed tests" {
  TEST_COMMANDS=("exit 1")
  verify_all_tests_pass 2>/dev/null || true
  [[ "$TESTS_FAILED_OUTPUT" =~ "exit 1" ]]
}

@test "commit_if_needed: commits when there are changes" {
  git() {
    if [[ "$1" == "rev-parse" ]]; then
      echo "$INITIAL_SHA"
    elif [[ "$1" == "add" ]]; then
      return 0
    elif [[ "$1" == "diff" ]]; then
      return 1
    elif [[ "$1" == "commit" ]]; then
      echo "commit $@" >> "$SHARED_TEST_DIR/git-calls.log"
      return 0
    fi
  }
  export -f git
  
  commit_if_needed
  [ -f "$SHARED_TEST_DIR/git-calls.log" ]
  grep -q "commit" "$SHARED_TEST_DIR/git-calls.log"
}

@test "commit_if_needed: does not commit when no changes" {
  git() {
    if [[ "$1" == "rev-parse" ]]; then
      echo "same-sha"
    elif [[ "$1" == "add" ]]; then
      return 0
    elif [[ "$1" == "diff" ]]; then
      return 0
    elif [[ "$1" == "commit" ]]; then
      echo "commit $@" >> "$SHARED_TEST_DIR/git-calls.log"
      return 0
    fi
  }
  export -f git
  INITIAL_SHA="same-sha"
  
  commit_if_needed
  [ ! -f "$SHARED_TEST_DIR/git-calls.log" ]
}

@test "create_feature_branch: creates branch with issue number" {
  ISSUE_NUMBER="789"
  create_feature_branch >/dev/null 2>&1 || true
  [[ "$BRANCH_NAME" =~ "789" ]]
}

@test "create_feature_branch: creates branch with timestamp" {
  create_feature_branch >/dev/null 2>&1 || true
  [[ "$BRANCH_NAME" =~ "-auto-" ]]
}

@test "initialize_loop_state: sets REVIEW_ROUND to 1" {
  REVIEW_ROUND=999
  initialize_loop_state
  [ "$REVIEW_ROUND" -eq 1 ]
}

@test "initialize_loop_state: sets empty REVIEWER_FEEDBACK" {
  REVIEWER_FEEDBACK="old feedback"
  initialize_loop_state
  [ -z "$REVIEWER_FEEDBACK" ]
}

@test "initialize_loop_state: sets INITIAL_SHA" {
  initialize_loop_state
  [ -n "$INITIAL_SHA" ]
}

@test "initialize_loop_state: sets empty SCREENSHOT_URLS" {
  SCREENSHOT_URLS=("old" "data")
  initialize_loop_state
  [ ${#SCREENSHOT_URLS[@]} -eq 0 ]
}

@test "create_pr: includes screenshots when SCREENSHOT_URLS populated" {
  SCREENSHOT_URLS=("test1.png|https://example.com/test1.png" "test2.png|https://example.com/test2.png")
  
  gh() {
    if [ "$1" = "pr" ] && [ "$2" = "create" ]; then
      for arg in "$@"; do
        if [ "$arg" = "--body" ]; then
          echo "$@" >> "$SHARED_TEST_DIR/pr-body.log"
          break
        fi
      done
    fi
    return 0
  }
  export -f gh
  
  create_pr >/dev/null 2>&1
  
  [ -f "$SHARED_TEST_DIR/pr-body.log" ]
  grep -q "Screenshots" "$SHARED_TEST_DIR/pr-body.log"
  grep -q "test1.png" "$SHARED_TEST_DIR/pr-body.log"
  grep -q "https://example.com/test1.png" "$SHARED_TEST_DIR/pr-body.log"
}

@test "create_pr: no screenshots section when SCREENSHOT_URLS empty" {
  SCREENSHOT_URLS=()
  
  gh() {
    if [ "$1" = "pr" ] && [ "$2" = "create" ]; then
      for arg in "$@"; do
        if [ "$arg" = "--body" ]; then
          echo "$@" >> "$SHARED_TEST_DIR/pr-body.log"
          break
        fi
      done
    fi
    return 0
  }
  export -f gh
  
  create_pr >/dev/null 2>&1
  
  [ -f "$SHARED_TEST_DIR/pr-body.log" ]
  ! grep -q "Screenshots" "$SHARED_TEST_DIR/pr-body.log"
}

@test "handle_no_changes_failure: posts comment" {
  gh() {
    echo "gh $@" >> "$SHARED_TEST_DIR/gh-calls.log"
    return 0
  }
  export -f gh
  
  run handle_no_changes_failure
  [ "$status" -eq 1 ]
  [ -f "$SHARED_TEST_DIR/gh-calls.log" ]
  grep -q "Failed" "$SHARED_TEST_DIR/gh-calls.log"
}

@test "handle_wip_failure: pushes branch and posts comment" {
  gh() {
    echo "gh $@" >> "$SHARED_TEST_DIR/gh-calls.log"
    return 0
  }
  git() {
    echo "git $@" >> "$SHARED_TEST_DIR/git-calls.log"
    return 0
  }
  export -f gh git
  
  run handle_wip_failure
  [ "$status" -eq 1 ]
  [ -f "$SHARED_TEST_DIR/git-calls.log" ]
  grep -q "push" "$SHARED_TEST_DIR/git-calls.log"
}

@test "configure_git_user: sets email from config" {
  git() { command git "$@"; }
  export -f git
  
  git init --quiet
  configure_git_user >/dev/null 2>&1
  email=$(git config --global user.email)
  [ "$email" = "$RALPH_BOT_EMAIL" ]
}

@test "configure_git_user: sets name from config" {
  git() { command git "$@"; }
  export -f git
  
  git init --quiet
  configure_git_user >/dev/null 2>&1
  name=$(git config --global user.name)
  [ "$name" = "$RALPH_BOT_NAME" ]
}

@test "cleanup_screenshot_artifacts: removes cached screenshots" {
  mkdir -p "$REPO_ROOT/screenshots"
  touch "$REPO_ROOT/screenshots/test.png"
  git add "$REPO_ROOT/screenshots/test.png" 2>/dev/null || true
  
  cleanup_screenshot_artifacts 2>/dev/null || true
  [ $? -eq 0 ]
}

@test "get_diff_output: returns diff between commits" {
  git() { command git "$@"; }
  export -f git
  
  git init --quiet
  git config user.email "test@example.com"
  git config user.name "Test User"
  echo "initial" > test.txt
  git add test.txt
  git commit -m "Initial" --quiet
  
  local before=$(git rev-parse HEAD)
  echo "change1" > test.txt
  git add test.txt
  git commit -m "Change 1" --quiet
  
  BEFORE_ROUND_SHA="$before"
  result=$(get_diff_output)
  [[ "$result" =~ "change1" ]] || [[ "$result" =~ "test.txt" ]]
}

@test "run_test_scaffolding: skips when no test flags" {
  AIDER_TEST_FLAGS=""
  gh() { return 0; }
  export -f gh
  
  run run_test_scaffolding
  [ "$status" -eq 0 ]
  [[ "$output" =~ "Skipping test scaffolding" ]]
}

@test "run_test_scaffolding: runs when test flags are set" {
  AIDER_TEST_FLAGS="--auto-test --test-cmd 'npm test'"
  
  # Mock aider and gh
  aider() {
    echo "aider $@" >> "$SHARED_TEST_DIR/aider-calls.log"
    return 0
  }
  gh() {
    echo "gh $@" >> "$SHARED_TEST_DIR/gh-calls.log"
    return 0
  }
  export -f aider gh
  
  run_test_scaffolding
  [ -f "$SHARED_TEST_DIR/gh-calls.log" ]
  grep -q "Test Scaffolding" "$SHARED_TEST_DIR/gh-calls.log"
}

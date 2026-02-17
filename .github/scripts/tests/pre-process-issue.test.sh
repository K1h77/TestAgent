#!/usr/bin/env bats

setup() {
  export TEST_DIR="$(mktemp -d)"
  export ISSUE_NUMBER="123"
  export GITHUB_REPOSITORY="test/repo"
  export OPENROUTER_API_KEY="test-key"
  
  source "${BATS_TEST_DIRNAME}/../../configure-ralph"
  export MODEL_REVIEWER="test-model"
  
  source "${BATS_TEST_DIRNAME}/../pre-process-issue.sh"
}

teardown() {
  rm -rf "$TEST_DIR"
  unset ISSUE_NUMBER GITHUB_REPOSITORY OPENROUTER_API_KEY MODEL_REVIEWER
  unset ISSUE_TITLE ISSUE_BODY ISSUE_LABELS ISSUE_DETAILS
  unset IMG_URLS IMG_MARKDOWNS ISSUE_IMAGES_DIR
}

@test "validate_environment: fails when ISSUE_NUMBER is missing" {
  unset ISSUE_NUMBER
  run validate_environment
  [ "$status" -eq 1 ]
  [[ "$output" =~ "requires ISSUE_NUMBER" ]]
}

@test "validate_environment: fails when GITHUB_REPOSITORY is missing" {
  unset GITHUB_REPOSITORY
  run validate_environment
  [ "$status" -eq 1 ]
  [[ "$output" =~ "requires" ]]
}

@test "validate_environment: succeeds when both vars are set" {
  run validate_environment
  [ "$status" -eq 0 ]
}

@test "fetch_issue_metadata: sets ISSUE_TITLE, ISSUE_BODY, ISSUE_LABELS" {
  REPO="test/repo"
  gh() {
    case "$7" in
      title) echo "Test Title" ;;
      body) echo "Test Body" ;;
      labels) echo "bug, feature" ;;
    esac
  }
  export -f gh
  
  fetch_issue_metadata
  [ "$ISSUE_TITLE" = "Test Title" ]
  [ "$ISSUE_BODY" = "Test Body" ]
  [ "$ISSUE_LABELS" = "bug, feature" ]
}

@test "extract_image_references: finds no images in plain text" {
  ISSUE_BODY="This is plain text with no images"
  extract_image_references
  [ "${#IMG_URLS[@]}" -eq 0 ]
  [ "${#IMG_MARKDOWNS[@]}" -eq 0 ]
}

@test "extract_image_references: finds single image" {
  ISSUE_BODY="Some text ![alt](https://example.com/img.png) more text"
  extract_image_references
  [ "${#IMG_URLS[@]}" -eq 1 ]
  [ "${IMG_URLS[0]}" = "https://example.com/img.png" ]
  [ "${IMG_MARKDOWNS[0]}" = "![alt](https://example.com/img.png)" ]
}

@test "extract_image_references: finds multiple images" {
  ISSUE_BODY="![img1](https://a.com/1.png) text ![img2](https://b.com/2.png)"
  extract_image_references
  [ "${#IMG_URLS[@]}" -eq 2 ]
  [ "${IMG_URLS[0]}" = "https://a.com/1.png" ]
  [ "${IMG_URLS[1]}" = "https://b.com/2.png" ]
}

@test "extract_image_references: handles URLs with query params" {
  ISSUE_BODY="![alt](https://example.com/img.png?size=large&v=2)"
  extract_image_references
  [ "${#IMG_URLS[@]}" -eq 1 ]
  [[ "${IMG_URLS[0]}" =~ "size=large" ]]
}

@test "download_image: returns success when curl succeeds" {
  curl() { echo "fake content" > "$3"; return 0; }
  export -f curl
  
  local test_file="$TEST_DIR/test.png"
  run download_image "https://example.com/img.png" "$test_file"
  [ "$status" -eq 0 ]
  [ -f "$test_file" ]
}

@test "download_image: returns failure when curl fails" {
  curl() { return 1; }
  export -f curl
  
  run download_image "https://example.com/img.png" "$TEST_DIR/test.png"
  [ "$status" -ne 0 ]
}

@test "download_image: returns failure when file is empty" {
  curl() { touch "$3"; return 0; }
  export -f curl
  
  run download_image "https://example.com/img.png" "$TEST_DIR/test.png"
  [ "$status" -ne 0 ]
}

@test "images are downloaded but body remains unmodified" {
  ISSUE_BODY="Text ![img](http://test.com/1.png) more text"
  ISSUE_TITLE="Test"
  ISSUE_LABELS=""
  IMG_URLS=("http://test.com/1.png")
  IMG_MARKDOWNS=()
  ISSUE_IMAGES_DIR="$TEST_DIR/images"
  mkdir -p "$ISSUE_IMAGES_DIR"
  
  curl() { echo "fake" > "$3"; return 0; }
  export -f curl
  
  build_issue_details
  
  # Body should remain unchanged (no replacement with descriptions)
  [[ "$ISSUE_DETAILS" =~ "![img](http://test.com/1.png)" ]]
  [[ ! "$ISSUE_DETAILS" =~ "IMAGE DESCRIPTION" ]]
}

@test "build_issue_details: creates formatted output" {
  ISSUE_TITLE="Test Title"
  ISSUE_BODY="Body content"
  ISSUE_LABELS="bug, p1"
  
  build_issue_details
  [[ "$ISSUE_DETAILS" =~ "Test Title" ]]
  [[ "$ISSUE_DETAILS" =~ "Body content" ]]
  [[ "$ISSUE_DETAILS" =~ "bug, p1" ]]
}

@test "build_issue_details: includes all sections" {
  ISSUE_TITLE="Title"
  ISSUE_BODY="Body"
  ISSUE_LABELS=""
  
  build_issue_details
  [[ "$ISSUE_DETAILS" =~ "Title:" ]]
  [[ "$ISSUE_DETAILS" =~ "Body:" ]]
  [[ "$ISSUE_DETAILS" =~ "Labels:" ]]
}

#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../configure-ralph"

validate_environment() {
  if [ -z "$ISSUE_NUMBER" ] || [ -z "$GITHUB_REPOSITORY" ]; then
    echo "❌ pre-process-issue.sh requires ISSUE_NUMBER and GITHUB_REPOSITORY env vars."
    exit 1
  fi
}

fetch_issue_metadata() {
  ISSUE_TITLE=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json title --jq '.title // ""')
  ISSUE_BODY=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json body --jq '.body // ""')
  ISSUE_LABELS=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json labels --jq '[.labels[].name] | join(", ")')
  echo "  Title: $ISSUE_TITLE"
}

extract_image_references() {
  IMG_URLS=()
  IMG_MARKDOWNS=()
  local img_count=0

  while IFS= read -r img_markdown; do
    if [ -n "$img_markdown" ]; then
      local img_url=$(echo "$img_markdown" | grep -oP '!\[.*?\]\(\K[^)]+' || true)
      if [ -n "$img_url" ]; then
        IMG_URLS+=("$img_url")
        IMG_MARKDOWNS+=("$img_markdown")
        img_count=$((img_count + 1))
      fi
    fi
  done <<< "$(echo "$ISSUE_BODY" | grep -oP '!\[.*?\]\([^)]+\)' || true)"

  echo "📷 [PRE-PROCESS] Found $img_count image(s) in issue body"
  return 0
}

download_image() {
  local url="$1"
  local output_file="$2"
  curl -sL -o "$output_file" "$url" 2>/dev/null && [ -s "$output_file" ]
}

build_issue_details() {
  ISSUE_DETAILS="Title: $ISSUE_TITLE

Body:
$ISSUE_BODY

Labels: $ISSUE_LABELS"
  
  echo ""
  echo "📋 [PRE-PROCESS] Final issue details:"
  echo "$ISSUE_DETAILS"
  echo ""
  echo "✅ [PRE-PROCESS] Done. ISSUE_DETAILS and ISSUE_IMAGES_DIR are ready."
}

main() {
  validate_environment
  
  REPO="$GITHUB_REPOSITORY"
  ISSUE_IMAGES_DIR="$RALPH_ISSUE_IMAGES_DIR"
  
  rm -rf "$ISSUE_IMAGES_DIR"
  mkdir -p "$ISSUE_IMAGES_DIR"
  
  echo "📖 [PRE-PROCESS] Fetching issue #$ISSUE_NUMBER..."
  fetch_issue_metadata
  extract_image_references
  
  # Download images for aider to read directly (no conversion to text)
  local image_count=${#IMG_URLS[@]}
  if [ $image_count -gt 0 ]; then
    echo "📷 [PRE-PROCESS] Downloading $image_count image(s)..."
    for i in $(seq 0 $((image_count - 1))); do
      local img_url="${IMG_URLS[$i]}"
      local img_file="$ISSUE_IMAGES_DIR/issue-image-$((i + 1)).png"
      echo "  Downloading: $img_url"
      if download_image "$img_url" "$img_file"; then
        echo "    ✅ Saved to: $img_file"
      else
        echo "    ⚠️  Download failed"
      fi
    done
  fi
  
  build_issue_details
}

if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
  main
fi

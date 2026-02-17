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
  ISSUE_TITLE=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json title --jq '.title // ""' 2>&1) || {
    echo "❌ [PRE-PROCESS] Failed to fetch issue #$ISSUE_NUMBER from $REPO. gh output:"
    echo "  $ISSUE_TITLE"
    echo "❌ [PRE-PROCESS] Check that the issue exists and GITHUB_TOKEN has read access."
    exit 1
  }
  
  if [ -z "$ISSUE_TITLE" ]; then
    echo "❌ [PRE-PROCESS] Issue #$ISSUE_NUMBER has no title. The issue may not exist or is inaccessible."
    exit 1
  fi
  
  ISSUE_BODY=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json body --jq '.body // ""' 2>&1) || {
    echo "❌ [PRE-PROCESS] Failed to fetch issue body for #$ISSUE_NUMBER."
    exit 1
  }
  
  if [ -z "$ISSUE_BODY" ]; then
    echo "⚠️  [PRE-PROCESS] Issue #$ISSUE_NUMBER has an empty body. The issue may lack sufficient detail for the agent."
  fi
  
  ISSUE_LABELS=$(gh issue view "$ISSUE_NUMBER" --repo "$REPO" --json labels --jq '[.labels[].name] | join(", ")' 2>/dev/null) || {
    echo "⚠️  [PRE-PROCESS] Could not fetch labels for issue #$ISSUE_NUMBER (non-fatal)."
    ISSUE_LABELS=""
  }
  
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
  
  # Final sanity check: ISSUE_DETAILS must contain meaningful content
  local stripped
  stripped=$(echo "$ISSUE_DETAILS" | sed 's/Title://;s/Body://;s/Labels://;s/[[:space:]]//g')
  if [ -z "$stripped" ]; then
    echo "❌ [PRE-PROCESS] ISSUE_DETAILS is effectively empty after assembly. Cannot proceed."
    echo "   Title='$ISSUE_TITLE' Body='$(echo "$ISSUE_BODY" | head -c 100)' Labels='$ISSUE_LABELS'"
    exit 1
  fi
  
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

# Always run main — this script is sourced by ralph.sh
# and needs to execute to populate ISSUE_DETAILS
main

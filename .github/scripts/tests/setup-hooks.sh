#!/usr/bin/env bash

echo "🔧 Setting up local testing..."
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
  echo "❌ Not in a git repository"
  exit 1
fi

PRE_COMMIT_HOOK="$HOOKS_DIR/pre-commit"
PRE_COMMIT_SOURCE="$SCRIPT_DIR/hooks/pre-commit"

if [ ! -f "$PRE_COMMIT_SOURCE" ]; then
  echo "❌ Pre-commit hook template not found at $PRE_COMMIT_SOURCE"
  exit 1
fi

if [ -f "$PRE_COMMIT_HOOK" ]; then
  echo "⚠️  Pre-commit hook already exists"
  read -p "Overwrite? (y/n) " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
fi

cp "$PRE_COMMIT_SOURCE" "$PRE_COMMIT_HOOK"
chmod +x "$PRE_COMMIT_HOOK"

echo "✅ Pre-commit hook installed"
echo ""
echo "Tests will now run automatically before each commit."
echo "To skip: git commit --no-verify"

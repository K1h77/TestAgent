#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

check_bats_installed() {
  if ! command -v bats &> /dev/null; then
    echo "❌ bats is not installed."
    echo ""
    echo "Install bats:"
    echo "  macOS:   brew install bats-core"
    echo "  Linux:   npm install -g bats"
    echo "  Manual:  git clone https://github.com/bats-core/bats-core.git && cd bats-core && ./install.sh /usr/local"
    exit 1
  fi
}

run_pre_process_tests() {
  echo "🧪 Running pre-process-issue.sh tests..."
  echo ""
  bats "$SCRIPT_DIR/pre-process-issue.test.sh"
}

run_ralph_tests() {
  echo "🧪 Running ralph.sh tests..."
  echo ""
  bats "$SCRIPT_DIR/ralph.test.sh"
}

run_all_tests() {
  run_pre_process_tests
  echo ""
  run_ralph_tests
}

show_usage() {
  echo "Usage: $0 [test-name]"
  echo ""
  echo "Available tests:"
  echo "  pre-process    Run pre-process-issue.sh tests"
  echo "  ralph          Run ralph.sh tests"
  echo "  all            Run all tests (default)"
  echo ""
  echo "Examples:"
  echo "  $0                    # Run all tests"
  echo "  $0 ralph              # Run only ralph.sh tests"
  echo "  $0 pre-process        # Run only pre-process-issue.sh tests"
}

main() {
  check_bats_installed
  
  case "${1:-all}" in
    pre-process|preprocess)
      run_pre_process_tests
      ;;
    ralph)
      run_ralph_tests
      ;;
    all)
      run_all_tests
      ;;
    -h|--help|help)
      show_usage
      exit 0
      ;;
    *)
      echo "❌ Unknown test: $1"
      echo ""
      show_usage
      exit 1
      ;;
  esac
}

main "$@"


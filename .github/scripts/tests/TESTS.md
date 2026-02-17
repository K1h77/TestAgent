# Test Suite Documentation

## Overview
Comprehensive unit tests for `pre-process-issue.sh` using the [bats-core](https://github.com/bats-core/bats-core) testing framework.

Location: `.github/scripts/tests/pre-process-issue.test.sh`

## Test Coverage

### Environment Validation (3 tests)
- Missing `ISSUE_NUMBER` env var
- Missing `GITHUB_REPOSITORY` env var  
- Both env vars present

### Issue Metadata Fetching (1 test)
- Fetches title, body, and labels from GitHub API

### Image Reference Extraction (4 tests)
- No images in plain text
- Single image detection
- Multiple images detection
- URLs with query parameters

### Image Download (3 tests)
- Successful download
- Failed curl request
- Empty file after download

### MIME Type Detection (4 tests)
- JPEG detection
- GIF detection
- WebP detection
- Default PNG fallback

### Vision Prompt Building (2 tests)
- Title placeholder presence
- Key instruction content

### Image Description Generation (2 tests)
- Successful API response
- Failed API response

### Markdown Replacement (3 tests)
- Basic replacement
- Special characters in description
- Exact match only (no fuzzy matching)

### Image Processing (3 tests)
- No images case
- Single image success
- Failed download handling

### Issue Details Building (2 tests)
- Formatted output structure
- All sections present

## Running Tests

### Prerequisites
Install bats-core:
```bash
# macOS
brew install bats-core

# Linux (via npm)
npm install -g bats

# Manual
git clone https://github.com/bats-core/bats-core.git
cd bats-core && ./install.sh /usr/local
```

### Execute
```bash
# Using test runner
bash .github/scripts/run-tests.sh

# Direct with bats
bats .github/scripts/tests/pre-process-issue.test.sh
```

## Test Strategy

### Mocking
External commands (`gh`, `curl`, `jq`, `base64`, `file`) are mocked using bash function overrides to:
- Isolate units under test
- Avoid network calls
- Ensure deterministic results

### Setup/Teardown
- `setup()`: Creates temp directories, sets env vars, sources script
- `teardown()`: Cleans temp files, unsets all globals

### Assertions
- Exit codes: `[ "$status" -eq 0 ]`
- Output matching: `[[ "$output" =~ "pattern" ]]`
- Variable checks: `[ "$VAR" = "expected" ]`

## Total Coverage
**31 tests** covering all 11 functions plus edge cases.

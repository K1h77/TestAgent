# Ralph Configuration Guide

All Ralph configuration values are centralized in [configure-ralph](.github/configure-ralph).

## Overview

The `configure-ralph` file contains all configuration values used across Ralph's scripts. It provides sensible defaults while allowing customization through environment variables.

## Configuration Variables

### AI Models

- **`RALPH_MODEL_ARCHITECT`** (default: `openrouter/anthropic/claude-haiku-4-5`)  
  Multi-modal AI model used as the architect/planner in aider's architect mode. This model can see images directly.

- **`RALPH_MODEL_ARCHITECT_HARD`** (default: `openrouter/anthropic/claude-sonnet-4-5`)  
  Upgraded architect model used when the issue has a `hard` label. Automatically swaps in for more complex problems that need stronger reasoning.

- **`RALPH_MODEL_CODER`** (default: `openrouter/minimax/minimax-m2.5`)  
  AI model used as the editor (code writer) in aider's architect mode.

- **`RALPH_MODEL_REVIEWER`** (default: `openrouter/anthropic/claude-haiku-4-5`)  
  AI model used for code review.

### Test Command Mapping

Issue labels can be mapped to test commands. When an issue has a matching label, the corresponding test command is passed to aider via `--auto-test --test-cmd`. Follow the naming convention `RALPH_TEST_CMD_<UPPERCASED_LABEL>`.

- **`RALPH_TEST_CMD_FRONTEND`** (default: empty)  
  Test command to run when the issue has the `frontend` label.  
  Example: `npm test --prefix frontend`

- **`RALPH_TEST_CMD_BACKEND`** (default: empty)  
  Test command to run when the issue has the `backend` label.  
  Example: `npm test --prefix backend`

You can add more labels by adding new variables following the same convention (e.g., `RALPH_TEST_CMD_API`, `RALPH_TEST_CMD_AUTH`). Don't forget to export them in `configure-ralph`.

### Review & PR Settings

- **`RALPH_MAX_REVIEW_ROUNDS`** (default: `3`)  
  Maximum number of coding/review iterations before giving up.

- **`RALPH_PR_SUMMARY_MAX_LINES`** (default: `10`)  
  Maximum lines to include in PR description from coding output.

- **`RALPH_PR_BASE_BRANCH`** (default: `main`)  
  Base branch for pull requests.

### Git Configuration

- **`RALPH_BOT_EMAIL`** (default: `ralph-bot@users.noreply.github.com`)  
  Git commit email for Ralph bot.

- **`RALPH_BOT_NAME`** (default: `Ralph Bot`)  
  Git commit author name for Ralph bot.

- **`RALPH_BRANCH_PREFIX`** (default: `fix/issue`)  
  Prefix for automatically created branches.

### Screenshot & Visual Testing

- **`RALPH_APP_URL`** (default: `http://localhost:3000`)  
  URL where the application runs for screenshot testing.

- **`RALPH_SERVER_STARTUP_WAIT`** (default: `30`)  
  Maximum seconds to wait for server startup.

- **`RALPH_SERVER_STARTUP_SLEEP`** (default: `1`)  
  Seconds to sleep between server startup checks.

- **`RALPH_SCREENSHOT_PREFIX`** (default: `visual-check`)  
  Prefix for screenshot filenames.

- **`RALPH_SCREENSHOT_DEFAULT_PAGES`** (default: `/`)  
  Comma-separated list of default pages to screenshot.

- **`RALPH_SCREENSHOT_VIEWPORT_WIDTH`** (default: `1280`)  
  Browser viewport width in pixels.

- **`RALPH_SCREENSHOT_VIEWPORT_HEIGHT`** (default: `720`)  
  Browser viewport height in pixels.

- **`RALPH_SCREENSHOT_TIMEOUT`** (default: `30000`)  
  Page load timeout in milliseconds.

- **`RALPH_SCREENSHOT_WAIT`** (default: `1000`)  
  Wait time after page load in milliseconds.

- **`RALPH_SCREENSHOT_TEXT_PREVIEW`** (default: `300`)  
  Characters of visible text to capture in full preview.

- **`RALPH_SCREENSHOT_TEXT_SHORT`** (default: `150`)  
  Characters of visible text to capture in short preview.

- **`RALPH_SCREENSHOT_RETENTION_DAYS`** (default: `7`)  
  Days to keep screenshot releases before cleanup.

### File & Path Settings

- **`RALPH_TEMP_DIR`** (default: `/tmp`)  
  Temporary directory for file operations.

- **`RALPH_ISSUE_IMAGES_DIR`** (default: `${RALPH_TEMP_DIR}/issue-images`)  
  Directory for downloaded issue images.

- **`RALPH_CHANGED_FILES_MAX`** (default: `20`)  
  Maximum number of changed files to track.

- **`RALPH_CHANGED_FILES_DISPLAY`** (default: `10`)  
  Maximum number of changed files to display in comments.

### Output & Summary Settings

- **`RALPH_SUMMARY_MAX_LINES`** (default: `20`)  
  Maximum lines to extract for summary sections.

### API Settings

- **`RALPH_OPENROUTER_API_URL`** (default: `https://openrouter.ai/api/v1/chat/completions`)  
  OpenRouter API endpoint URL.

## Customization

### Method 1: Environment Variables

Set environment variables before running Ralph scripts:

```bash
export RALPH_MODEL_CODER="openrouter/anthropic/claude-3.5-sonnet"
export RALPH_MAX_REVIEW_ROUNDS=5
.github/scripts/ralph.sh
```

### Method 2: Modify configure-ralph

Edit [configure-ralph](.github/configure-ralph) to change defaults:

```bash
RALPH_MAX_REVIEW_ROUNDS="${RALPH_MAX_REVIEW_ROUNDS:-5}"
```

### Method 3: GitHub Actions Workflow

Set environment variables in [.github/workflows/ralph.yaml](.github/workflows/ralph.yaml):

```yaml
- name: Run Ralph Agent
  env:
    RALPH_MODEL_CODER: "openrouter/anthropic/claude-3.5-sonnet"
    RALPH_MAX_REVIEW_ROUNDS: "5"
  run: .github/scripts/ralph.sh
```

## Files Using Configuration

- **ralph.sh** - Main agent orchestration
- **pre-process-issue.sh** - Issue and image preprocessing
- **playwright-screenshot.sh** - Screenshot automation
- **visual-check.js** - Playwright screenshot capture
- **tests/pre-process-issue.test.sh** - Unit tests

All scripts source `configure-ralph` automatically - no manual configuration needed in each file.

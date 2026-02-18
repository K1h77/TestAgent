# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Ralph Agent** — an autonomous GitHub issue resolution system. When an issue is labeled `ralph-autofix`, it reads the issue, creates a branch, drives Cline CLI through a TDD loop, takes before/after screenshots (for frontend issues), commits changes, opens a PR, and runs a self-review cycle.

Everything outside `.github/` is a **placeholder testbed** (simple Node.js/Express task manager) used to test the agent. The real code lives in `.github/`.

## Commands

### Python agent tests (the primary tests to run when editing agent code)
```bash
# All agent tests
python -m pytest .github/scripts/tests/ -v --tb=short

# Single test file
python -m pytest .github/scripts/tests/test_issue_parser.py -v

# Single test by name
python -m pytest .github/scripts/tests/test_issue_parser.py::TestParseIssue::test_valid_input -v

# Syntax-check all agent Python files
find .github/scripts -name "*.py" | xargs python -m py_compile
```

### Testbed (Node.js)
```bash
npm ci                          # install deps
npm test                        # Jest unit + Playwright E2E
npm run test:unit               # Jest only
npm run test:e2e                # Playwright only
npx jest backend/__tests__/foo.test.js   # single Jest test
cd backend && npm start         # start server on :3000
```

### Python dependencies
```bash
pip install -r requirements.txt   # aider-chat, pytest>=8.0, pyyaml>=6.0
```

## Architecture

### Agent pipeline (`.github/scripts/`)

The pipeline has two phases, each a separate Python entry point:

1. **`ralph_agent.py`** — Main orchestration: parse issue → create branch → TDD coding loop (up to `max_coding_attempts` retries) → screenshots (frontend only) → commit/push → create PR
2. **`self_review.py`** — Self-review: fresh read-only Cline reviewer → parse verdict (`LGTM` / `NEEDS CHANGES`) → if rejected, fixer Cline + self-heal loop → re-review (up to `max_review_iterations`)

### Library modules (`.github/scripts/lib/`)

| Module | Purpose |
|---|---|
| `agent_config.py` | Loads `.github/agent_config.yml` into frozen dataclasses (`AgentConfig`, `Models`, `Retries`, `Timeouts`). LRU-cached — single source of truth for all config. |
| `cline_runner.py` | Subprocess wrapper for Cline CLI. Manages isolated `.cline-*` directories, streams stdout/stderr via threads, detects stuck patterns, tracks OpenRouter cost per run. |
| `git_ops.py` | Git + `gh` CLI operations (branch, commit, push, PR creation, comments, labels). Raises `GitError`. |
| `issue_parser.py` | Parses/validates GitHub issue env vars into an `Issue` dataclass. `require_env()` raises `ValueError` on missing vars. |
| `logging_config.py` | Structured logging setup + markdown summary formatters for issue/PR comments. |
| `screenshot.py` | Before/after screenshots via Playwright MCP through a vision-capable Cline instance. Writes visual verdict file for review injection. |

### Key design patterns

- **All config in `agent_config.yml`** — models, retry counts, timeouts. Never hardcode these in Python.
- **Fail-fast with explicit exceptions** — `ClineError`, `GitError`, `ValueError` for missing env vars. Nothing proceeds silently.
- **Isolated Cline directories** — each Cline instance (`.cline-agent/`, `.cline-vision/`, `.cline-reviewer-N/`, `.cline-fixer-N/`) gets its own `globalState.json` + `secrets.json`. These dirs are `.gitignore`d and scrubbed in CI.
- **Prompt templates with `{{PLACEHOLDER}}`** — all prompts live in `scripts/prompts/`. `load_prompt_template()` / `load_template()` do string replacement.
- **Frontend gating via `issue.is_frontend()`** — server startup, screenshots, and visual QA only run when the issue has a `frontend` label.
- **Lenient verdict parsing** — `parse_verdict()` defaults to `LGTM` if no clear verdict is found (benefit of the doubt).

### CI/CD (`.github/workflows/`)

- **`ralph-dispatch.yml`** — Triggered by `issues: [labeled]`. If label is `ralph-autofix`, removes it (prevents re-trigger) and dispatches the main workflow.
- **`ralph-autofix.yml`** — `workflow_dispatch` on `ubuntu-latest`, 90-minute timeout. Requires `OPENROUTER_API_KEY` secret. Steps: checkout → setup Node 22 + Python 3.12 → install deps → validate API key → syntax-check + pytest → run `ralph_agent.py` → scrub secrets → upload screenshots → run `self_review.py`.

### Models (via OpenRouter, not Anthropic direct)

Configured in `agent_config.yml`: `coding` and `fixer` use DeepSeek, `coding_plan` and `reviewer` use MiniMax, `vision` uses Qwen VL.

## Required Environment Variables

| Variable | Description |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter API key for all Cline model calls |
| `ISSUE_NUMBER`, `ISSUE_TITLE`, `ISSUE_BODY` | GitHub issue metadata |
| `ISSUE_LABELS` | Comma-separated labels (optional, enables frontend gating) |
| `GITHUB_TOKEN` | For `gh` CLI operations (auto-set in CI) |
| `PR_NUMBER`, `BRANCH` | Required by `self_review.py` (output from `ralph_agent.py` step) |

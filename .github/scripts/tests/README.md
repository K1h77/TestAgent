# Tests Directory

## Quick Start

### Windows
```powershell
.github/scripts/tests/run-tests.ps1
```

### macOS / Linux
```bash
bash .github/scripts/tests/run-tests.sh
```

## Files

| File | Purpose |
|------|---------|
| `pre-process-issue.test.sh` | 31 unit tests for pre-process-issue.sh |
| `run-tests.sh` | Bash test runner |
| `run-tests.ps1` | PowerShell test runner (Windows) |
| `setup-hooks.sh` | Install git pre-commit hook |
| `hooks/pre-commit` | Pre-commit hook template |
| `TESTS.md` | Detailed test documentation |
| `LOCAL_TESTING.md` | Local setup guide |

## Prerequisites

**Required:**
- bash (Git Bash on Windows, or WSL, or native)
- bats-core: `npm install -g bats-core`

**Optional (for some tests):**
- jq: JSON processor
- curl: HTTP requests

## Setup Pre-commit Hook

```bash
bash .github/scripts/tests/setup-hooks.sh
```

Tests will run automatically before each commit.

## CI/CD

Tests also run on GitHub Actions via `.github/workflows/test.yml`

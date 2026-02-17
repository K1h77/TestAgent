# Scripts Directory

## Core Scripts

| Script | Purpose | OS |
|--------|---------|-----|
| `pre-process-issue.sh` | Convert GitHub issue images → text descriptions | Linux/macOS/WSL |
| `ralph.sh` | Main agent orchestrator (coding + review loop) | Linux/macOS/WSL |
| `playwright-screenshot.sh` | Take app screenshots for visual verification | Linux/macOS/WSL |
| `visual-check.js` | Playwright script that captures and reports screenshots | Any (Node.js) |

## Testing

All testing files are in the `tests/` subdirectory.

**Run tests:**
- Windows: `.github/scripts/tests/run-tests.ps1`
- macOS/Linux: `bash .github/scripts/tests/run-tests.sh`

See [tests/README.md](tests/README.md) for details.

# Dependencies

TestAgent uses multiple package managers for different components.

## Installation

### Quick Setup
```bash
npm run setup
```

This will:
1. Install Node.js dependencies
2. Install system packages (on supported platforms)
3. Set up git pre-commit hooks

### Manual Setup

#### 1. System Packages (.github/apt-packages.txt)
Linux (Ubuntu/Debian):
```bash
sudo apt-get install $(cat .github/apt-packages.txt)
```

macOS:
```bash
brew install jq curl perl
```

Windows:
```powershell
choco install jq curl
```

Installs:
- `jq` - JSON processor (required by clanker.sh and pre-process-issue.sh)
- `curl` - HTTP client (required for API calls)
- `perl` - Text processing (required by pre-process-issue.sh)

#### 2. Node.js Dependencies (package.json)
```bash
npm install
```

Installs:
- `bats` - Test framework
- `playwright` - Browser automation for visual testing

#### 3. Python Dependencies (requirements.txt)
```bash
pip install -r requirements.txt
```

Installs:
- `aider-chat` - AI pair programming tool used by Ralph

## Dependency Files

| File | Purpose | Package Manager |
|------|---------|----------------|
| `package.json` | Node.js dependencies & scripts | npm |
| `requirements.txt` | Python dependencies | pip |
| `.github/apt-packages.txt` | System-level packages | apt/brew/choco |

## CI/CD

GitHub Actions automatically installs all dependencies from these files in both workflows:
- `.github/workflows/clanker.yaml` - Production agent runs
- `.github/workflows/test.yml` - Test suite runs

Installation order: System packages → Python packages → Node.js packages

## Development

After installing dependencies, you can:
```bash
# Run tests
npm test

# Watch tests (re-run on file changes)
npm run test:watch

# Set up git hooks
npm run setup:hooks
```

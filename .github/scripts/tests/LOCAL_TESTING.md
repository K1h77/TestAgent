# Local Test Setup

## Quick Start

### One-Command Setup (Recommended)
```bash
npm run setup
```

This installs all dependencies and sets up git hooks.

### Windows (PowerShell)
```powershell
.github/scripts/run-tests.ps1
```

The PowerShell runner will:
1. ✅ Detect bash (Git Bash, WSL, or system bash)
2. 📦 Install bats-core if needed (via npm)
3. 🚀 Run all tests
4. ✅ Report results

### macOS / Linux (bash)
```bash
bash .github/scripts/run-tests.sh
```

## Prerequisites

### Option 1: Git Bash (Easiest on Windows)
Git Bash comes with Git for Windows:
- Download: https://git-scm.com/download/win
- Install with default options
- PowerShell runner will auto-detect

### Option 2: WSL2 (Best for development)
```powershell
wsl --install Ubuntu
# Then in WSL terminal:
sudo apt-get install -y bats jq curl
```

### Option 3: npm (For any system with Node.js)
```bash
npm install -g bats-core
```

## Automated Testing on Commit

### Set Up Pre-commit Hook

Copy the git hook:
```bash
cp .github/scripts/hooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Now tests will run automatically before each commit. If they fail, the commit is blocked.

### Disable Hook (if needed)
```bash
git commit --no-verify
```

## Troubleshooting

### "bash not found"
Install Git for Windows or WSL

### "bats not found"
```bash
npm install -g bats-core
```

### "jq not found"
```bash
# macOS
brew install jq

# Windows (with Chocolatey)
choco install jq

# Linux
sudo apt-get install jq
```

### PowerShell execution policy error
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## CI/CD

Tests also run automatically on every push/PR via GitHub Actions.

See `.github/workflows/test.yml` for CI configuration.

# Running Tests

## Quick Start

### Run All Tests
```bash
# Linux/macOS
./run-tests.sh

# Windows PowerShell
.\run-tests.ps1
```

### Run Specific Test Suites

#### Ralph Tests Only
```bash
# Linux/macOS
./run-tests.sh ralph

# Windows PowerShell
.\run-tests.ps1 ralph
```

#### Pre-Process Tests Only
```bash
# Linux/macOS
./run-tests.sh pre-process

# Windows PowerShell
.\run-tests.ps1 pre-process
```

## Direct BATS Execution

You can also run tests directly with `bats`:

```bash
# Run specific test file
bats pre-process-issue.test.sh
bats ralph.test.sh

# Run all test files
bats *.test.sh
```

## Available Test Suites

- **`ralph`** - Tests for [ralph.sh](../ralph.sh) main agent logic
- **`pre-process`** - Tests for [pre-process-issue.sh](../pre-process-issue.sh) image processing

## Help

```bash
./run-tests.sh --help
```

## Test Output

- ✓ = Test passed
- ✗ = Test failed
- Number = Test count

Example output:
```
🧪 Running ralph.sh tests...

 ✓ validate_environment: fails when ISSUE_NUMBER is missing
 ✓ validate_environment: succeeds when both vars are set
 ✓ extract_summary: extracts content between marker and next heading
 
3 tests, 0 failures
```

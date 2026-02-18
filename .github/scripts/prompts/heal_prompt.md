# Fix Failing Tests for Issue #{{ISSUE_NUMBER}}

## Context
You previously wrote code to fix issue #{{ISSUE_NUMBER}} ("{{ISSUE_TITLE}}"), but the tests are failing.

## Test Output
```
{{TEST_OUTPUT}}
```

## Instructions
1. Analyze the test failures carefully
2. Fix the IMPLEMENTATION code to make the tests pass
3. Do NOT change the test expectations unless the test itself has a clear bug
4. The tests define the correct behavior — your job is to make the code match
5. After fixing, run the tests again to verify:
   ```bash
   cd backend && npx jest --passWithNoTests
   npx playwright test
   ```

## Rules
- Fix implementation, not tests (unless the test has an obvious bug)
- Keep changes minimal
- Do not introduce new features or refactor unrelated code

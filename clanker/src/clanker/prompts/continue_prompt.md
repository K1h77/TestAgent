# Continue: Resolve GitHub Issue #{{ISSUE_NUMBER}}

## Context
You previously started working on issue #{{ISSUE_NUMBER}} ("{{ISSUE_TITLE}}") but the session ended before completion (timeout or error). **Do not start over** — continue from where you left off.

## Original Issue
{{ISSUE_BODY}}

## Progress So Far
Here is the git diff of changes already made:
```diff
{{GIT_DIFF}}
```

## Test Results
```
{{TEST_OUTPUT}}
```

## What To Do
1. Review the diff above to understand what was already done
2. If tests are failing, fix the implementation (not the tests)
3. If tests don't exist yet, create them following the TDD process
4. If implementation is incomplete, finish it
5. Run tests to verify everything passes:
   ```bash
   cd backend && npx jest --passWithNoTests
   npx playwright test
   ```

## Rules
- Do NOT redo work that's already done (check the diff)
- Do NOT delete or rewrite files that are already correct
- Fix implementation, not test expectations
- Keep changes minimal and focused on the issue

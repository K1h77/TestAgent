# Task: Resolve GitHub Issue #{{ISSUE_NUMBER}}

## Issue Title
{{ISSUE_TITLE}}

## Issue Description
{{ISSUE_BODY}}

## Repository Structure
- `backend/` — Express.js API server (port 3000), entry point: `backend/server.js`
- `frontend/` — Vanilla JS frontend (`index.html`, `app.js`, `styles.css`)
- The backend serves frontend static files from `../frontend`
- In-memory task storage (no database)
- The backend server is already running on http://localhost:3000

## MANDATORY TDD Process — You MUST Follow This Exactly

### Step 1: Analyze the Issue
Read and understand the issue. Identify what files need to change and what behavior is expected.

### Step 2: Write Failing Tests FIRST
Before writing ANY implementation code:

1. **For backend/API changes** — create Jest tests:
   - Directory: `backend/__tests__/`
   - Install Jest if not present: `npm install --save-dev jest` in the backend directory
   - Add `"test": "jest --passWithNoTests"` to `backend/package.json` scripts if missing
   - Write tests that describe the EXPECTED behavior
   - Example: testing a new endpoint, testing validation, testing error responses

2. **For frontend/UI changes** — create Playwright E2E tests:
   - Directory: `tests/e2e/`
   - Write tests using `@playwright/test`
   - Test user-visible behavior (elements exist, interactions work, correct content displays)

3. **For both API + UI changes** — write both types of tests

### Step 3: Run Tests — Confirm They FAIL
```bash
cd backend && npx jest --passWithNoTests
npx playwright test
```
The tests MUST fail at this point. If they pass, your tests aren't testing the right thing.

### Step 4: Implement the Fix
Now implement the minimal code changes to make the failing tests pass.
- Modify only what is necessary
- Follow existing code style and patterns
- Do not introduce unnecessary dependencies
- Do not refactor unrelated code

### Step 5: Run Tests — Confirm They PASS
```bash
cd backend && npx jest --passWithNoTests
npx playwright test
```
All tests must pass.

### Step 6: Visual Verification (UI changes only)
If this issue involves any UI changes:
1. Use the Playwright MCP server to navigate to http://localhost:3000
2. If there's a login form, enter any credentials and submit
3. Take a screenshot to verify the UI looks correct
4. Save to `{{SCREENSHOTS_DIR}}/after.png`

## Rules
- NEVER skip writing tests first
- NEVER modify test expectations just to make them pass — fix the implementation instead
- Keep changes minimal and focused on the issue
- Do not refactor unrelated code
- Do not add features beyond what the issue requests

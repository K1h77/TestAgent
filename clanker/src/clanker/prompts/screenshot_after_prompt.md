Using the Playwright MCP server for browser automation, do a focused visual QA
for GitHub issue #{{ISSUE_NUMBER}}: {{ISSUE_TITLE}}
Issue description: {{ISSUE_BODY}}

**Note:** You may use shell commands for file I/O operations (writing verdict file).

## What changed (frontend files only)
The following diff shows exactly which HTML/CSS/JS/TS files were modified.
Use this to know *where* to look — focus only on the areas the diff touches.

```diff
{{FRONTEND_DIFF}}
```

## Instructions — be fast and focused, complete all 3 steps

**Be efficient: aim for 3–5 Playwright actions total. Do not explore unrelated parts of the app.**

### Step 1 — Navigate and capture screenshots (max 3 screenshots)
1. Navigate to http://localhost:3000
2. If a login form is present, log in with username 'testuser' and password 'password'
3. Go directly to the area changed by the diff and capture screenshots using FULL PATHS:
   - **{{SCREENSHOTS_DIR}}/after_01.png** — the default/idle state of the changed feature
   - **{{SCREENSHOTS_DIR}}/after_02.png** — the feature after one key interaction (e.g. click, submit, toggle) if relevant
   - **{{SCREENSHOTS_DIR}}/after_03.png** — one extra state only if clearly needed
4. Verify screenshots were saved: run `ls {{SCREENSHOTS_DIR}}` to confirm PNG files exist

   Do NOT take more than 3 screenshots. Do NOT explore unrelated pages.

### Step 2 — Visual QA assessment
Look at your screenshots and assess:
- Is the feature from the issue visible and functioning?
- Are there any obvious visual problems? (blank page, broken layout, missing elements,
  severe CSS issues)

Be lenient — only flag clear, obvious problems. Minor styling differences are fine.

### Step 3 — Write verdict file immediately after screenshots (do NOT skip)
Write results to: {{VERDICT_PATH}}
The file must contain exactly 2 lines:
  Line 1 — verdict (choose one):
    VISUAL: OK
    VISUAL: FEATURE_NOT_FOUND - <what you expected to see but didn't>
    VISUAL: ISSUE - <brief description of the problem>
  
  Line 2 — selected screenshots (MUST be on separate line):
    SELECTED: after_01.png, after_02.png

Example (notice the two separate lines):
  VISUAL: OK
  SELECTED: after_01.png, after_02.png

IMPORTANT:
- Writing the verdict file is mandatory — do it immediately after taking screenshots.
- Use shell commands (echo/write-output) to create {{VERDICT_PATH}} with the exact format above.
- Do not keep exploring after you have enough to make a verdict.

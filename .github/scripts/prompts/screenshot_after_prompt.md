Using the Playwright MCP server ONLY (do NOT read files or run shell commands),
do a thorough visual QA for GitHub issue #{{ISSUE_NUMBER}}: {{ISSUE_TITLE}}
Issue description: {{ISSUE_BODY}}

## Step 1 — Explore and capture screenshots
1. Launch a browser and navigate to http://localhost:3000
2. If a login form is present, log in with username 'testuser' and password 'password'
3. Explore the app thoroughly to verify the feature described in the issue.
   Take as many screenshots as you need to check:
   - The feature in its default/idle state
   - The feature after interaction (e.g. toggle activated, modal open, state changed)
   - Any other relevant pages or states that help confirm the fix is complete
   Save each screenshot to the directory: {{SCREENSHOTS_DIR}}
   Name them sequentially: after_01.png, after_02.png, after_03.png, etc.

## Step 2 — Visual QA review
Review all the screenshots you took and assess:
- Is the feature described in the issue clearly visible and working?
- Are there any obvious visual glitches? (broken layout, overlapping elements,
  blank/white page, missing content, severe CSS issues, console errors visible on screen)

Be lenient — only flag clear, obvious problems. Minor styling differences are fine.

## Step 3 — Write verdict and selected screenshots to file
Write results to: {{VERDICT_PATH}}
The file must contain:
  Line 1: exactly one verdict:
    VISUAL: OK
    VISUAL: FEATURE_NOT_FOUND - <what you expected to see but didn't>
    VISUAL: ISSUE - <brief description of the glitch or problem>
  Line 2: SELECTED: <comma-separated list of the screenshot filenames that best show the result>
    Choose only the most informative ones (1-3 is ideal). Example:
    SELECTED: after_01.png, after_02.png

Example file contents:
  VISUAL: OK
  SELECTED: after_01.png, after_02.png

IMPORTANT: Use only Playwright MCP tools. Do not run npm, cat, ls, or any shell commands.

Using the Playwright MCP server ONLY (do NOT read files or run shell commands),
take a BEFORE screenshot of the app as it currently exists.

Issue #{{ISSUE_NUMBER}}: {{ISSUE_TITLE}}
Description: {{ISSUE_BODY}}

Steps:
1. Launch a browser and navigate to http://localhost:3000
2. If a login form is present, log in with username 'testuser' and password 'password'
3. Using the app's own navigation (links, buttons, menus), navigate to the page or section
   where the feature described in the issue will likely be added.
   This feature does NOT exist yet — do not search for it or try to interact with it.
   Just get to the right area of the app.
4. Once on the relevant page, immediately use the Playwright MCP screenshot tool to take a
   full-page screenshot and save it to: {{OUTPUT_PATH}}

CRITICAL: This is a BEFORE screenshot. The feature has NOT been implemented yet.
If you cannot find a UI element related to the issue, that is expected — just take the
screenshot of the current page and stop. Do NOT spend time searching or retrying.
Use only Playwright MCP tools. Do not run npm, cat, ls, or any shell commands.

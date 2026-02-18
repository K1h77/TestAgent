"""Before/after screenshot management via Cline + Playwright MCP.

Takes screenshots by prompting Cline with the multimodal model to use
the Playwright MCP server. Validates that screenshots were actually
created and provides markdown embedding for PR bodies.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ScreenshotError(Exception):
    """Raised when screenshot capture fails."""
    pass


SCREENSHOT_PROMPT_TEMPLATE = (
    "Using the Playwright MCP server ONLY (do NOT read files or run shell commands), "
    "capture a '{label}' screenshot for this GitHub issue:\n"
    "\n"
    "Issue #{issue_number}: {issue_title}\n"
    "Description: {issue_body}\n"
    "\n"
    "Steps:\n"
    "1. Launch a browser and navigate to http://localhost:3000\n"
    "2. If a login form is present, log in with username 'testuser' and password 'password'\n"
    "3. Based on the issue description, navigate to the relevant page and trigger the "
    "relevant UI state using only Playwright browser interactions (click, navigate, fill, etc.). "
    "For example: if the issue mentions a settings page, click through to it; if it mentions "
    "a toggle or switch, click it; if it mentions a modal, open it. "
    "Use the page's own navigation (links, buttons, menus) to get there — do NOT run shell "
    "commands or read source files to figure out routes.\n"
    "4. Once the relevant state is visible, take a full-page screenshot and save it to: {output_path}\n"
    "\n"
    "IMPORTANT: Use only Playwright MCP tools. Do not run npm, cat, ls, or any shell commands."
)


def take_screenshot(
    cline_runner,
    output_path: Path,
    label: str,
    issue_number: int = 0,
    issue_title: str = "",
    issue_body: str = "",
) -> Optional[Path]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prompt = SCREENSHOT_PROMPT_TEMPLATE.format(
        output_path=str(output_path),
        label=label,
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body[:2000],
    )

    logger.info(f"Taking '{label}' screenshot → {output_path}")

    try:
        cline_runner.run(prompt, timeout=300)
    except Exception as e:
        logger.warning(
            f"Screenshot '{label}' failed (non-blocking): {e}. "
            f"Continuing without screenshot."
        )
        return None

    # Validate the screenshot was actually created
    if not output_path.exists():
        # Fallback: log any PNGs that were actually saved in the directory
        saved = list(output_path.parent.glob("*.png"))
        if saved:
            names = ", ".join(p.name for p in saved)
            logger.warning(
                f"Screenshot '{label}' was not saved at expected path {output_path}. "
                f"Cline saved these files instead (check prompt): {names}. "
                f"Continuing without screenshot."
            )
        else:
            logger.warning(
                f"Screenshot '{label}' was not created at {output_path}. "
                f"Cline may not have saved the file. Continuing without screenshot."
            )
        return None

    file_size = output_path.stat().st_size
    if file_size == 0:
        logger.warning(f"Screenshot '{label}' at {output_path} is empty (0 bytes).")
        return None

    logger.info(f"Screenshot '{label}' saved: {output_path} ({file_size} bytes)")
    return output_path


def embed_screenshots_markdown(
    before_path: Optional[Path],
    after_path: Optional[Path],
    branch: str,
    repo: str,
) -> str:
    lines = ["### Screenshots", ""]

    if before_path is None and after_path is None:
        lines.append("*No screenshots captured.*")
        return "\n".join(lines)

    base_url = f"https://raw.githubusercontent.com/{repo}/{branch}"

    if before_path is not None:
        # Convert to repo-relative path
        relative = _to_relative_path(before_path)
        lines.append("**Before:**")
        lines.append(f"![Before]({base_url}/{relative})")
        lines.append("")

    if after_path is not None:
        relative = _to_relative_path(after_path)
        lines.append("**After:**")
        lines.append(f"![After]({base_url}/{relative})")
        lines.append("")

    return "\n".join(lines)


def _to_relative_path(path: Path) -> str:
    parts = Path(path).parts
    for i, part in enumerate(parts):
        if part == "screenshots":
            return "/".join(parts[i:])
    return Path(path).name

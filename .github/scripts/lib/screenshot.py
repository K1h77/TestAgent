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
    "Using the Playwright MCP server, do the following:\n"
    "1. Navigate to http://localhost:3000\n"
    "2. If there is a login form, enter 'testuser' as username and 'password' as password and submit\n"
    "3. Wait for the main page to fully load\n"
    "4. Take a screenshot and save it to: {output_path}\n"
    "\n"
    "This is the '{label}' screenshot. Make sure the screenshot captures the full page."
)


def take_screenshot(cline_runner, output_path: Path, label: str) -> Optional[Path]:
    """Take a screenshot using Cline + Playwright MCP.

    Args:
        cline_runner: ClineRunner instance (should use multimodal model).
        output_path: Where to save the screenshot.
        label: Label for logging ('before' or 'after').

    Returns:
        Path to the screenshot if successful, None if screenshot failed
        (screenshots are non-blocking — failure is logged as warning).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prompt = SCREENSHOT_PROMPT_TEMPLATE.format(
        output_path=str(output_path),
        label=label,
    )

    logger.info(f"Taking '{label}' screenshot → {output_path}")

    try:
        cline_runner.run(prompt, timeout=120)
    except Exception as e:
        logger.warning(
            f"Screenshot '{label}' failed (non-blocking): {e}. "
            f"Continuing without screenshot."
        )
        return None

    # Validate the screenshot was actually created
    if not output_path.exists():
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
    """Generate markdown for embedding before/after screenshots in PR body.

    Uses raw GitHub URLs so images render directly in the PR.

    Args:
        before_path: Path to before screenshot (or None).
        after_path: Path to after screenshot (or None).
        branch: Git branch name.
        repo: GitHub repo in 'owner/repo' format.

    Returns:
        Markdown string with embedded images.
    """
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
    """Convert an absolute path to a repo-relative path.

    Looks for 'screenshots/' in the path and returns from that point.
    Falls back to the filename if the pattern isn't found.
    """
    parts = Path(path).parts
    for i, part in enumerate(parts):
        if part == "screenshots":
            return "/".join(parts[i:])
    return Path(path).name

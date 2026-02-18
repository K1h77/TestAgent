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
    "\n"
    "## Context\n"
    "You are capturing a '{label}' screenshot for this GitHub issue:\n"
    "- **Issue #{issue_number}:** {issue_title}\n"
    "- **Description:** {issue_body}\n"
    "\n"
    "## Instructions\n"
    "The app is running at http://localhost:3000.\n"
    "Based on the issue description, figure out which page and interaction "
    "best demonstrates the relevant area of the app. This may involve:\n"
    "- Navigating to a specific route (not just the homepage)\n"
    "- Clicking buttons, filling out forms, or triggering UI states\n"
    "- Scrolling to a specific section\n"
    "\n"
    "If there is a login form blocking you, use 'testuser' / 'password'.\n"
    "\n"
    "Once you have navigated to the relevant state, take a full-page screenshot "
    "and save it to: {output_path}\n"
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

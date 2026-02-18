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
    "3. Navigate to the most relevant page for this issue using the app's own navigation "
    "(links, buttons, menus). Do NOT run shell commands or read source files.\n"
    "   - If this is a 'before' screenshot: the feature described in the issue may not exist yet. "
    "Just navigate to where it would logically appear and take the screenshot as-is.\n"
    "   - If this is an 'after' screenshot: the feature should now be implemented. Interact with it "
    "(e.g. click the toggle, open the modal, trigger the UI state) so the screenshot shows it working.\n"
    "4. Once the relevant state is visible, take a full-page screenshot and save it to: {output_path}\n"
    "\n"
    "IMPORTANT: Use only Playwright MCP tools. Do not run npm, cat, ls, or any shell commands."
)

AFTER_SCREENSHOT_REVIEW_PROMPT_TEMPLATE = (
    "Using the Playwright MCP server ONLY (do NOT read files or run shell commands), "
    "do the following for GitHub issue #{issue_number}: {issue_title}\n"
    "Issue description: {issue_body}\n"
    "\n"
    "## Step 1 — Take the after screenshot\n"
    "1. Launch a browser and navigate to http://localhost:3000\n"
    "2. If a login form is present, log in with username 'testuser' and password 'password'\n"
    "3. Navigate to the relevant page and interact with the feature described in the issue "
    "(e.g. click the toggle, open the modal). Use only the app's own navigation.\n"
    "4. Take a full-page screenshot and save it to: {output_path}\n"
    "\n"
    "## Step 2 — Visual QA review\n"
    "Now look at the screenshot you just took and answer these questions:\n"
    "- Is the feature described in the issue clearly visible and working in the screenshot?\n"
    "- Are there any obvious visual glitches? (broken layout, overlapping elements, "
    "blank/white page, missing content, severe CSS issues, console errors visible on screen)\n"
    "\n"
    "Be lenient — only flag clear, obvious problems. Minor styling differences are fine.\n"
    "\n"
    "## Step 3 — Write verdict to file\n"
    "Write a short verdict to the file: {verdict_path}\n"
    "The file must contain exactly one of these verdicts on the first line, "
    "followed by an optional short explanation:\n"
    "  VISUAL: OK\n"
    "  VISUAL: FEATURE_NOT_FOUND - <what you expected to see but didn't>\n"
    "  VISUAL: ISSUE - <brief description of the glitch or problem>\n"
    "\n"
    "Example file contents:\n"
    "  VISUAL: ISSUE - Dark mode toggle is present but the page background stays white after clicking it\n"
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
    timeout: int = 300,
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
        cline_runner.run(prompt, timeout=timeout)
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


def take_after_screenshot_with_review(
    cline_runner,
    output_path: Path,
    issue_number: int = 0,
    issue_title: str = "",
    issue_body: str = "",
    timeout: int = 300,
) -> tuple[Optional[Path], Optional[Path]]:
    """Take the after screenshot and run an inline visual QA review.

    Returns (screenshot_path, verdict_path). Either may be None on failure.
    The verdict file contains a VISUAL: OK / FEATURE_NOT_FOUND / ISSUE line.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    verdict_path = output_path.parent / "visual_verdict.txt"

    prompt = AFTER_SCREENSHOT_REVIEW_PROMPT_TEMPLATE.format(
        output_path=str(output_path),
        verdict_path=str(verdict_path),
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body[:2000],
    )

    logger.info(f"Taking 'after' screenshot + visual review → {output_path}")

    try:
        cline_runner.run(prompt, timeout=timeout)
    except Exception as e:
        logger.warning(
            f"After screenshot/review failed (non-blocking): {e}. "
            f"Continuing without screenshot."
        )
        return None, None

    result_path = output_path if output_path.exists() and output_path.stat().st_size > 0 else None
    result_verdict = verdict_path if verdict_path.exists() and verdict_path.stat().st_size > 0 else None

    if result_path:
        logger.info(f"After screenshot saved: {output_path} ({output_path.stat().st_size} bytes)")
    else:
        logger.warning(f"After screenshot not created at {output_path}")

    if result_verdict:
        verdict_text = verdict_path.read_text(encoding="utf-8").strip().splitlines()[0]
        logger.info(f"Visual verdict: {verdict_text}")
    else:
        logger.warning("Visual verdict file not written by model")

    return result_path, result_verdict


def read_visual_verdict(screenshots_dir: Path) -> Optional[str]:
    """Read the visual verdict file written during after-screenshot review.

    Returns the full file contents, or None if not found.
    """
    verdict_path = Path(screenshots_dir) / "visual_verdict.txt"
    if not verdict_path.exists():
        return None
    content = verdict_path.read_text(encoding="utf-8").strip()
    return content if content else None


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
    "4. Once the relevant state is visible, use the Playwright MCP screenshot tool to take a "
    "full-page screenshot and save it to: {output_path}\n"
    "\n"
    "IMPORTANT: Use only Playwright MCP tools. Do not run npm, cat, ls, or any shell commands."
)

AFTER_SCREENSHOT_REVIEW_PROMPT_TEMPLATE = (
    "Using the Playwright MCP server ONLY (do NOT read files or run shell commands), "
    "do a thorough visual QA for GitHub issue #{issue_number}: {issue_title}\n"
    "Issue description: {issue_body}\n"
    "\n"
    "## Step 1 — Explore and capture screenshots\n"
    "1. Launch a browser and navigate to http://localhost:3000\n"
    "2. If a login form is present, log in with username 'testuser' and password 'password'\n"
    "3. Explore the app thoroughly to verify the feature described in the issue. "
    "Take as many screenshots as you need to check:\n"
    "   - The feature in its default/idle state\n"
    "   - The feature after interaction (e.g. toggle activated, modal open, state changed)\n"
    "   - Any other relevant pages or states that help confirm the fix is complete\n"
    "   Save each screenshot to the directory: {screenshots_dir}\n"
    "   Name them sequentially: after_01.png, after_02.png, after_03.png, etc.\n"
    "\n"
    "## Step 2 — Visual QA review\n"
    "Review all the screenshots you took and assess:\n"
    "- Is the feature described in the issue clearly visible and working?\n"
    "- Are there any obvious visual glitches? (broken layout, overlapping elements, "
    "blank/white page, missing content, severe CSS issues, console errors visible on screen)\n"
    "\n"
    "Be lenient — only flag clear, obvious problems. Minor styling differences are fine.\n"
    "\n"
    "## Step 3 — Write verdict and selected screenshots to file\n"
    "Write results to: {verdict_path}\n"
    "The file must contain:\n"
    "  Line 1: exactly one verdict:\n"
    "    VISUAL: OK\n"
    "    VISUAL: FEATURE_NOT_FOUND - <what you expected to see but didn't>\n"
    "    VISUAL: ISSUE - <brief description of the glitch or problem>\n"
    "  Line 2: SELECTED: <comma-separated list of the screenshot filenames that best show the result>\n"
    "    Choose only the most informative ones (1-3 is ideal). Example:\n"
    "    SELECTED: after_01.png, after_02.png\n"
    "\n"
    "Example file contents:\n"
    "  VISUAL: OK\n"
    "  SELECTED: after_01.png, after_02.png\n"
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
        # Fallback: if Cline saved a PNG anywhere in the directory under a different name,
        # adopt the most recently modified one rather than dropping the screenshot entirely.
        saved = sorted(output_path.parent.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        if saved:
            best = saved[0]
            logger.warning(
                f"Screenshot '{label}' not at expected path {output_path.name}. "
                f"Cline saved '{best.name}' instead — renaming to {output_path.name}."
            )
            best.rename(output_path)
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
    after_paths: list[Path],
    branch: str,
    repo: str,
) -> str:
    lines = ["### Screenshots", ""]

    if before_path is None and not after_paths:
        lines.append("*No screenshots captured.*")
        return "\n".join(lines)

    base_url = f"https://raw.githubusercontent.com/{repo}/{branch}"

    if before_path is not None:
        relative = _to_relative_path(before_path)
        lines.append("**Before:**")
        lines.append(f"![Before]({base_url}/{relative})")
        lines.append("")

    if after_paths:
        lines.append("**After:**")
        for i, p in enumerate(after_paths, 1):
            relative = _to_relative_path(p)
            label = f"After {i}" if len(after_paths) > 1 else "After"
            lines.append(f"![{label}]({base_url}/{relative})")
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
) -> tuple[list[Path], Optional[Path]]:
    """Take after screenshots and run an inline visual QA review.

    The agent may take multiple screenshots and selects the most useful subset.
    Returns (selected_screenshot_paths, verdict_path). List may be empty on failure.
    The verdict file contains a VISUAL: OK / FEATURE_NOT_FOUND / ISSUE line.
    """
    output_path = Path(output_path)
    screenshots_dir = output_path.parent
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = screenshots_dir / "visual_verdict.txt"

    prompt = AFTER_SCREENSHOT_REVIEW_PROMPT_TEMPLATE.format(
        screenshots_dir=str(screenshots_dir),
        verdict_path=str(verdict_path),
        issue_number=issue_number,
        issue_title=issue_title,
        issue_body=issue_body[:2000],
    )

    logger.info(f"Taking 'after' screenshots + visual review → {screenshots_dir}")

    try:
        cline_runner.run(prompt, timeout=timeout)
    except Exception as e:
        logger.warning(
            f"After screenshot/review failed (non-blocking): {e}. "
            f"Continuing without screenshot."
        )
        return [], None

    # Parse the SELECTED: line from the verdict file to get the chosen screenshots
    selected_paths: list[Path] = []
    result_verdict = verdict_path if verdict_path.exists() and verdict_path.stat().st_size > 0 else None

    if result_verdict:
        verdict_text = verdict_path.read_text(encoding="utf-8").strip()
        logger.info(f"Visual verdict: {verdict_text.splitlines()[0]}")
        for line in verdict_text.splitlines():
            if line.strip().upper().startswith("SELECTED:"):
                names = line.split(":", 1)[1].strip()
                for name in names.split(","):
                    name = name.strip()
                    if name:
                        p = screenshots_dir / name
                        if p.exists() and p.stat().st_size > 0:
                            selected_paths.append(p)
                        else:
                            logger.warning(f"Selected screenshot not found or empty: {p}")
                break
    else:
        logger.warning("Visual verdict file not written by model")

    # Fallback: if no valid selections, use all PNGs in the dir that look like after_*.png
    if not selected_paths:
        candidates = sorted(screenshots_dir.glob("after_*.png"), key=lambda p: p.name)
        if not candidates:
            # Last resort: any PNG in the dir
            candidates = sorted(screenshots_dir.glob("*.png"), key=lambda p: p.stat().st_mtime)
        selected_paths = [p for p in candidates if p.stat().st_size > 0]
        if selected_paths:
            logger.warning(
                f"No SELECTED line in verdict — falling back to all captured PNGs: "
                f"{[p.name for p in selected_paths]}"
            )

    logger.info(f"After screenshots selected: {[p.name for p in selected_paths]}")
    return selected_paths, result_verdict


def read_visual_verdict(screenshots_dir: Path) -> Optional[str]:
    """Read the visual verdict file written during after-screenshot review.

    Returns the full file contents, or None if not found.
    """
    verdict_path = Path(screenshots_dir) / "visual_verdict.txt"
    if not verdict_path.exists():
        return None
    content = verdict_path.read_text(encoding="utf-8").strip()
    return content if content else None


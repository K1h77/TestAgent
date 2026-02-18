"""Before/after screenshot management via Cline + Playwright MCP.

Takes screenshots by prompting Cline with the multimodal model to use
the Playwright MCP server. Validates that screenshots were actually
created and provides markdown embedding for PR bodies.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class ScreenshotError(Exception):
    """Raised when screenshot capture fails."""
    pass


def _load_prompt(name: str, **kwargs: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Screenshot prompt template not found: {path}")
    content = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


def take_screenshot(
    cline_runner,
    output_path: Path,
    issue_number: int = 0,
    issue_title: str = "",
    issue_body: str = "",
    timeout: int = 300,
) -> Optional[Path]:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    prompt = _load_prompt(
        "screenshot_before_prompt.md",
        OUTPUT_PATH=str(output_path),
        ISSUE_NUMBER=str(issue_number),
        ISSUE_TITLE=issue_title,
        ISSUE_BODY=issue_body[:2000],
    )

    logger.info(f"Taking 'before' screenshot → {output_path}")

    try:
        cline_runner.run(prompt, timeout=timeout)
    except Exception as e:
        logger.warning(
            f"Before screenshot failed (non-blocking): {e}. "
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
                f"Before screenshot not at expected path {output_path.name}. "
                f"Cline saved '{best.name}' instead — renaming to {output_path.name}."
            )
            best.rename(output_path)
        else:
            logger.warning(
                f"Before screenshot was not created at {output_path}. "
                f"Cline may not have saved the file. Continuing without screenshot."
            )
            return None

    file_size = output_path.stat().st_size
    if file_size == 0:
        logger.warning(f"Before screenshot at {output_path} is empty (0 bytes).")
        return None

    logger.info(f"Before screenshot saved: {output_path} ({file_size} bytes)")
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
    frontend_diff: str = "",
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

    prompt = _load_prompt(
        "screenshot_after_prompt.md",
        SCREENSHOTS_DIR=str(screenshots_dir),
        VERDICT_PATH=str(verdict_path),
        ISSUE_NUMBER=str(issue_number),
        ISSUE_TITLE=issue_title,
        ISSUE_BODY=issue_body[:2000],
        FRONTEND_DIFF=frontend_diff[:6000] if frontend_diff else "(no frontend files changed)",
    )

    logger.info(f"Taking 'after' screenshots + visual review → {screenshots_dir}")

    cline_error: Optional[Exception] = None
    try:
        cline_runner.run(prompt, timeout=timeout)
    except Exception as e:
        cline_error = e
        logger.warning(
            f"After screenshot/review Cline exited with error (non-blocking): {e}. "
            f"Will still recover any screenshots saved before the crash."
        )

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

    if cline_error and not selected_paths:
        logger.warning("Cline errored and no screenshots were recovered. Continuing without.")
        return [], None

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


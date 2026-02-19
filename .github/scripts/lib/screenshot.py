import re
import logging
from pathlib import Path
from typing import Optional

from lib.utils import load_prompt_template, embed_screenshots_markdown, screenshot_relative_path, read_visual_verdict

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_to_relative_path = screenshot_relative_path


class ScreenshotError(Exception):
    pass


def _recover_misnamed_screenshot(output_path: Path) -> Optional[Path]:
    saved = sorted(output_path.parent.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not saved:
        return None
    best = saved[0]
    logger.warning(
        f"Before screenshot not at expected path {output_path.name}. "
        f"Cline saved '{best.name}' instead — renaming to {output_path.name}."
    )
    best.rename(output_path)
    return output_path


def _validate_screenshot(output_path: Path) -> Optional[Path]:
    if not output_path.exists():
        recovered = _recover_misnamed_screenshot(output_path)
        if not recovered:
            logger.warning(
                f"Before screenshot was not created at {output_path}. "
                f"Cline may not have saved the file. Continuing without screenshot."
            )
            return None
        output_path = recovered
    if output_path.stat().st_size == 0:
        logger.warning(f"Before screenshot at {output_path} is empty (0 bytes).")
        return None
    return output_path


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

    prompt = load_prompt_template(
        PROMPTS_DIR,
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
        logger.warning(f"Before screenshot failed (non-blocking): {e}. Continuing without screenshot.")
        return None

    result = _validate_screenshot(output_path)
    if result:
        logger.info(f"Before screenshot saved: {result} ({result.stat().st_size} bytes)")
    return result


def _run_after_screenshot_cline(
    cline_runner, screenshots_dir, verdict_path,
    issue_number, issue_title, issue_body, frontend_diff, timeout,
) -> Optional[Exception]:
    prompt = load_prompt_template(
        PROMPTS_DIR,
        "screenshot_after_prompt.md",
        SCREENSHOTS_DIR=str(screenshots_dir),
        VERDICT_PATH=str(verdict_path),
        ISSUE_NUMBER=str(issue_number),
        ISSUE_TITLE=issue_title,
        ISSUE_BODY=issue_body[:2000],
        FRONTEND_DIFF=frontend_diff[:6000] if frontend_diff else "(no frontend files changed)",
    )
    logger.info(f"Taking 'after' screenshots + visual review → {screenshots_dir}")
    try:
        cline_runner.run(prompt, timeout=timeout)
        return None
    except Exception as e:
        logger.warning(
            f"After screenshot/review Cline exited with error (non-blocking): {e}. "
            f"Will still recover any screenshots saved before the crash."
        )
        return e


def _parse_selected_paths(verdict_path: Path, screenshots_dir: Path) -> list[Path]:
    if not (verdict_path.exists() and verdict_path.stat().st_size > 0):
        logger.warning("Visual verdict file not written by model")
        return []
    verdict_text = verdict_path.read_text(encoding="utf-8").strip()
    logger.info(f"Visual verdict: {verdict_text.splitlines()[0]}")
    match = re.search(r"SELECTED:\s*([^\n]+)", verdict_text, re.IGNORECASE)
    if not match:
        logger.warning("No SELECTED line found in verdict file")
        return []
    selected = []
    for name in match.group(1).strip().split(","):
        name = name.strip()
        if name and name.endswith(".png"):
            p = screenshots_dir / name
            if p.exists() and p.stat().st_size > 0:
                selected.append(p)
            else:
                logger.warning(f"Selected screenshot not found or empty: {p}")
    return selected


def _fallback_screenshot_selection(screenshots_dir: Path) -> list[Path]:
    candidates = sorted(screenshots_dir.glob("after_*.png"), key=lambda p: p.name)
    if not candidates:
        candidates = sorted(
            (p for p in screenshots_dir.glob("*.png") if p.name != "before.png"),
            key=lambda p: p.stat().st_mtime,
        )
    return [p for p in candidates if p.stat().st_size > 0]


def take_after_screenshot_with_review(
    cline_runner,
    output_path: Path,
    issue_number: int = 0,
    issue_title: str = "",
    issue_body: str = "",
    frontend_diff: str = "",
    timeout: int = 300,
) -> tuple[list[Path], Optional[Path]]:
    output_path = Path(output_path)
    screenshots_dir = output_path.parent
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = screenshots_dir / "visual_verdict.txt"

    cline_error = _run_after_screenshot_cline(
        cline_runner, screenshots_dir, verdict_path,
        issue_number, issue_title, issue_body, frontend_diff, timeout,
    )

    result_verdict = verdict_path if verdict_path.exists() and verdict_path.stat().st_size > 0 else None
    selected_paths = _parse_selected_paths(verdict_path, screenshots_dir)

    if not selected_paths:
        selected_paths = _fallback_screenshot_selection(screenshots_dir)
        if selected_paths:
            logger.info(
                f"No valid SELECTED line in verdict — using all captured after screenshots: "
                f"{[p.name for p in selected_paths]}"
            )
        else:
            logger.warning("No screenshots found in directory at all")

    logger.info(f"After screenshots selected: {[p.name for p in selected_paths]}")

    if cline_error and not selected_paths:
        logger.warning("Cline errored and no screenshots were recovered. Continuing without.")
        return [], None

    return selected_paths, result_verdict


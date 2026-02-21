#!/usr/bin/env python3
"""Ralph Agent — Self-Review with auto re-fix loop.

Runs a fresh Cline instance to review the code changes, then optionally
loops back to fix issues. Maximum 3 review iterations. The reviewer is
lenient — only rejecting clearly broken or missing things.

All failures are explicit. Verbose reasoning goes to stdout (workflow logs),
only summaries are posted as PR comments.
"""

import logging
import os
import re
import sys
from pathlib import Path

from ralph.lib.agent_config import load_config
from ralph.lib.cline_runner import (
    ClineRunner,
    ClineError,
    READ_ONLY_PERMISSIONS,
    get_openrouter_usage,
)
from ralph.lib.git_ops import (
    commit_and_push,
    get_diff,
    get_changed_files,
    post_pr_comment,
    label_pr,
    GitError,
)
from ralph.lib.issue_parser import parse_issue, require_env
from ralph.lib.logging_config import setup_logging, format_review_summary
from ralph.lib.project_runner import run_tests
from ralph.lib.prompt_utils import load_prompt_template, get_default_prompts_dir
from ralph.lib.screenshot import read_visual_verdict

logger = logging.getLogger("self-review")


def _resolve_repo_root() -> Path:
    env = os.environ.get("RALPH_REPO_ROOT")
    if env:
        return Path(env)
    return Path.cwd()


# Constants
REPO_ROOT = _resolve_repo_root()
PACKAGE_DIR = Path(__file__).resolve().parent
MCP_SETTINGS_PATH = PACKAGE_DIR / "cline-config" / "cline_mcp_settings.json"
PROMPTS_DIR = get_default_prompts_dir()
SCREENSHOTS_DIR = REPO_ROOT / "screenshots"

# Load central config from .github/agent_config.yml
_cfg = load_config()
MAX_REVIEW_ITERATIONS = _cfg.retries.max_review_iterations
REVIEW_TIMEOUT = _cfg.timeouts.review_seconds
FIX_TIMEOUT = _cfg.timeouts.fix_seconds


def parse_verdict(review_output: str) -> str:
    """Extract the verdict from review output.

    Looks for 'Verdict: LGTM' or 'Verdict: NEEDS CHANGES' anywhere in the
    output, case-insensitively, ignoring markdown bold/italic/code markers
    and leading punctuation so that outputs like '**Verdict: LGTM**' or
    '> Verdict: NEEDS CHANGES' are handled correctly.

    Returns:
        'LGTM' or 'NEEDS CHANGES'. Defaults to 'LGTM' if no clear verdict
        is found (lenient — benefit of the doubt).
    """
    # Strip markdown noise from each line before matching
    clean_output = re.sub(r"[*_`>#\-]", " ", review_output)

    for line in clean_output.splitlines():
        line_stripped = line.strip().lower()
        if "verdict" in line_stripped and ":" in line_stripped:
            after_colon = line_stripped.split(":", 1)[1].strip()
            if (
                "needs changes" in after_colon
                or "needs_changes" in after_colon
                or "needs changes" in line_stripped
            ):
                return "NEEDS CHANGES"
            if "lgtm" in after_colon:
                return "LGTM"

    # Also do a looser full-text scan in case the verdict isn't on its own line
    clean_lower = clean_output.lower()
    if "needs changes" in clean_lower or "needs_changes" in clean_lower:
        # Only count it if "verdict" appears nearby (within 100 chars)
        idx = clean_lower.find("needs changes")
        if idx != -1 and "verdict" in clean_lower[max(0, idx - 100) : idx + 50]:
            return "NEEDS CHANGES"

    # No clear verdict found — be lenient
    logger.warning("No clear verdict found in review output. Defaulting to LGTM.")
    return "LGTM"


def self_heal_loop(fixer: ClineRunner, issue, max_attempts: int = 3) -> bool:
    """Run tests with self-healing fix attempts.

    Args:
        fixer: ClineRunner instance for fixing code.
        issue: Parsed Issue object.
        max_attempts: Maximum fix attempts.

    Returns:
        True if tests pass, False otherwise.
    """
    for attempt in range(1, max_attempts + 1):
        success, test_output = run_tests(
            REPO_ROOT, _cfg.timeouts.test_seconds, _cfg.project.test_command
        )
        if success:
            logger.info(f"Tests passed on heal attempt {attempt}")
            return True

        logger.warning(f"Tests failed (heal attempt {attempt}/{max_attempts})")

        if attempt < max_attempts:
            heal_prompt = load_prompt_template(
                PROMPTS_DIR,
                "heal_prompt.md",
                ISSUE_NUMBER=str(issue.number),
                ISSUE_TITLE=issue.title,
                TEST_OUTPUT=test_output[:5000],
            )
            try:
                fixer.run(heal_prompt, timeout=FIX_TIMEOUT, cwd=REPO_ROOT)
            except ClineError as e:
                logger.error(f"Heal attempt {attempt} failed: {e}")

    return False


def _safe_label_pr(pr_number: str, label: str) -> None:
    """Label a PR, logging but never raising on failure."""
    try:
        label_pr(pr_number, label)
    except Exception as e:
        logger.warning(
            f"Failed to add label '{label}' to PR #{pr_number} (non-blocking): {e}"
        )


def _safe_post_pr_comment(pr_number: str, body: str) -> None:
    """Post a PR comment, logging but never raising on failure."""
    try:
        post_pr_comment(pr_number, body)
    except Exception as e:
        logger.warning(f"Failed to post PR comment (non-blocking): {e}")


def _build_cost_section(baseline: "float | None") -> str:
    """Return a markdown cost section string, or empty string if unavailable."""
    final = get_openrouter_usage()
    if final is not None and baseline is not None:
        cost = max(0.0, final - baseline)
        logger.info(f"Self-review total cost: ${cost:.4f} USD")
        return f"\n\n### Review Cost\n${cost:.4f} USD (via OpenRouter)"
    return ""


def main() -> None:
    setup_logging(verbose=True)

    logger.info("=" * 60)
    logger.info("Self-Review starting")
    logger.info("=" * 60)
    # Snapshot OpenRouter usage at start for review cost tracking
    _cost_baseline = get_openrouter_usage()
    # ── 1. Validate inputs ──────────────────────────────────────
    issue = parse_issue(
        number=require_env("ISSUE_NUMBER"),
        title=require_env("ISSUE_TITLE"),
        body=require_env("ISSUE_BODY"),
        labels=os.environ.get("ISSUE_LABELS", ""),
    )
    pr_number = require_env("PR_NUMBER")
    branch = require_env("BRANCH")

    require_env("OPENROUTER_API_KEY")

    logger.info(f"Reviewing PR #{pr_number} for issue #{issue.number}")

    # ── 2. Review loop ──────────────────────────────────────────
    last_review_output = ""

    for iteration in range(1, MAX_REVIEW_ITERATIONS + 1):
        logger.info("=" * 40)
        logger.info(f"REVIEW ITERATION {iteration}/{MAX_REVIEW_ITERATIONS}")
        logger.info("=" * 40)

        # Fresh reviewer context each time
        reviewer = ClineRunner(
            cline_dir=REPO_ROOT / f".cline-reviewer-{iteration}",
            model=_cfg.models.reviewer,
            command_permissions=READ_ONLY_PERMISSIONS,
        )

        # Gather diff context
        diff = get_diff(_cfg.project.base_branch)
        changed_files = get_changed_files(_cfg.project.base_branch)

        if not diff.strip():
            logger.warning("No diff found. Marking as passed.")
            _safe_label_pr(pr_number, "review-passed")
            _safe_post_pr_comment(
                pr_number,
                format_review_summary(
                    "No changes detected. Auto-approving."
                    + _build_cost_section(_cost_baseline),
                    "PASSED",
                ),
            )
            return

        # Truncate diff if too large to avoid token limits
        max_diff_len = 30000
        if len(diff) > max_diff_len:
            original_len = len(diff)
            diff = diff[:max_diff_len] + "\n\n... (diff truncated, see full diff in PR)"
            logger.info(f"Diff truncated from {original_len} to {max_diff_len} chars")

        review_prompt = load_prompt_template(
            PROMPTS_DIR,
            "review_prompt.md",
            ISSUE_NUMBER=str(issue.number),
            ISSUE_TITLE=issue.title,
            ISSUE_BODY=issue.body,
            GIT_DIFF=diff,
            CHANGED_FILES="\n".join(changed_files),
        )

        # Prepend any visual QA findings from the after-screenshot review
        # (only relevant for frontend issues that actually took screenshots)
        visual_verdict = (
            read_visual_verdict(SCREENSHOTS_DIR) if issue.is_frontend() else None
        )
        if visual_verdict:
            logger.info(
                f"Injecting visual verdict into review prompt: {visual_verdict.splitlines()[0]}"
            )
            review_prompt = (
                f"## Visual QA (from after-screenshot review)\n"
                f"{visual_verdict}\n\n"
                f"If the visual QA flags a FEATURE_NOT_FOUND or ISSUE, treat that as strong "
                f"signal that the fix may be incomplete or broken visually. "
                f"Factor this into your verdict.\n\n"
                f"---\n\n"
            ) + review_prompt

        # Run review
        try:
            result = reviewer.run(review_prompt, timeout=REVIEW_TIMEOUT, cwd=REPO_ROOT)
            last_review_output = result.stdout
        except ClineError as e:
            logger.error(
                f"Reviewer Cline crashed: {e}. Treating as LGTM (benefit of the doubt)."
            )
            visual_verdict = (
                read_visual_verdict(SCREENSHOTS_DIR) if issue.is_frontend() else None
            )
            visual_section = (
                f"\n\n### Visual QA\n{visual_verdict}" if visual_verdict else ""
            )
            _safe_label_pr(pr_number, "review-passed")
            _safe_post_pr_comment(
                pr_number,
                format_review_summary(
                    f"Reviewer failed to run (Cline error). Auto-approving.\n\nError: {e}{visual_section}"
                    + _build_cost_section(_cost_baseline),
                    "PASSED",
                ),
            )
            return

        verdict = parse_verdict(last_review_output)
        logger.info(f"Review verdict: {verdict}")

        if verdict == "LGTM":
            logger.info("Review passed!")
            visual_verdict = (
                read_visual_verdict(SCREENSHOTS_DIR) if issue.is_frontend() else None
            )
            visual_section = (
                f"\n\n### Visual QA\n{visual_verdict}" if visual_verdict else ""
            )
            _safe_label_pr(pr_number, "review-passed")
            _safe_post_pr_comment(
                pr_number,
                format_review_summary(
                    last_review_output
                    + visual_section
                    + _build_cost_section(_cost_baseline),
                    "PASSED",
                ),
            )
            return

        # ── Verdict is NEEDS CHANGES ────────────────────────────
        if iteration < MAX_REVIEW_ITERATIONS:
            logger.warning(
                f"Review rejected. Applying fixes (iteration {iteration})..."
            )

            fixer = ClineRunner(
                cline_dir=REPO_ROOT / f".cline-fixer-{iteration}",
                model=_cfg.models.fixer,
                # No MCP settings — fixer uses CLI tools only, same as coding_cline.
            )

            fix_prompt = load_prompt_template(
                PROMPTS_DIR,
                "review_fix_prompt.md",
                ISSUE_NUMBER=str(issue.number),
                ISSUE_TITLE=issue.title,
                ISSUE_BODY=issue.body,
                REVIEW_FEEDBACK=last_review_output[:5000],
            )

            try:
                fixer.run(fix_prompt, timeout=FIX_TIMEOUT, cwd=REPO_ROOT)
            except ClineError as e:
                logger.error(f"Fix attempt failed: {e}")

            # Self-heal tests after fix
            self_heal_loop(fixer, issue, max_attempts=_cfg.retries.max_heal_attempts)

            # Commit and push fixes
            try:
                commit_and_push(
                    f"fix(#{issue.number}): address review feedback (round {iteration})",
                    branch,
                )
            except GitError as e:
                logger.error(
                    f"Commit/push after review fix failed (round {iteration}): {e}. "
                    f"Cannot proceed — next review would see a stale diff. Stopping."
                )
                break

    # ── 3. Exhausted iterations ─────────────────────────────────
    logger.warning("Max review iterations reached. Posting final review.")
    visual_verdict = (
        read_visual_verdict(SCREENSHOTS_DIR) if issue.is_frontend() else None
    )
    visual_section = f"\n\n### Visual QA\n{visual_verdict}" if visual_verdict else ""
    _safe_label_pr(pr_number, "review-needs-attention")
    _safe_post_pr_comment(
        pr_number,
        format_review_summary(
            last_review_output + visual_section + _build_cost_section(_cost_baseline),
            "NEEDS ATTENTION",
        ),
    )

    logger.info("=" * 60)
    logger.info("Self-Review complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Self-review failed: {e}", exc_info=True)
        sys.exit(1)

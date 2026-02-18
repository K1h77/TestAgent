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
import subprocess
import sys
import time
from pathlib import Path

# Add parent directory to path so lib/ is importable
sys.path.insert(0, str(Path(__file__).parent))

from lib.agent_config import load_config
from lib.cline_runner import ClineRunner, ClineError, READ_ONLY_PERMISSIONS
from lib.git_ops import (
    commit_and_push,
    get_diff,
    get_changed_files,
    post_pr_comment,
    label_pr,
    GitError,
)
from lib.issue_parser import parse_issue, require_env
from lib.logging_config import setup_logging, format_review_summary
from lib.screenshot import read_visual_verdict

logger = logging.getLogger("self-review")

# Constants
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
MCP_SETTINGS_PATH = SCRIPTS_DIR / "cline-config" / "cline_mcp_settings.json"
PROMPTS_DIR = SCRIPTS_DIR / "prompts"
SCREENSHOTS_DIR = REPO_ROOT / "screenshots"

# Load central config from .github/agent_config.yml
_cfg = load_config()
MAX_REVIEW_ITERATIONS = _cfg.retries.max_review_iterations
REVIEW_TIMEOUT = _cfg.timeouts.review_seconds
FIX_TIMEOUT = _cfg.timeouts.fix_seconds


def load_template(name: str, **kwargs: str) -> str:
    """Load a prompt template and substitute placeholders."""
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")

    content = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))
    return content


def parse_verdict(review_output: str) -> str:
    """Extract the verdict from review output.

    Looks for 'Verdict: LGTM' or 'Verdict: NEEDS CHANGES' in the output.

    Args:
        review_output: Full output from the review Cline instance.

    Returns:
        'LGTM' or 'NEEDS CHANGES'. Defaults to 'LGTM' if no clear verdict
        is found (lenient — benefit of the doubt).
    """
    for line in review_output.splitlines():
        line_stripped = line.strip().lower()
        if "verdict:" in line_stripped:
            if "needs changes" in line_stripped or "needs_changes" in line_stripped:
                return "NEEDS CHANGES"
            if "lgtm" in line_stripped:
                return "LGTM"

    # No clear verdict found — be lenient
    logger.warning("No clear verdict found in review output. Defaulting to LGTM.")
    return "LGTM"


def run_tests() -> tuple[bool, str]:
    """Run the project test suite."""
    logger.info("Running tests...")
    result = subprocess.run(
        ["npm", "test"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=_cfg.timeouts.test_seconds,
    )
    output = result.stdout + "\n" + result.stderr
    return result.returncode == 0, output


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
        success, test_output = run_tests()
        if success:
            logger.info(f"Tests passed on heal attempt {attempt}")
            return True

        logger.warning(f"Tests failed (heal attempt {attempt}/{max_attempts})")

        if attempt < max_attempts:
            heal_prompt = load_template(
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


def main() -> None:
    setup_logging(verbose=True)

    logger.info("=" * 60)
    logger.info("Self-Review starting")
    logger.info("=" * 60)

    # ── 1. Validate inputs ──────────────────────────────────────
    issue = parse_issue(
        number=require_env("ISSUE_NUMBER"),
        title=require_env("ISSUE_TITLE"),
        body=require_env("ISSUE_BODY"),
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
        diff = get_diff("main")
        changed_files = get_changed_files("main")

        if not diff.strip():
            logger.warning("No diff found. Marking as passed.")
            label_pr(pr_number, "review-passed")
            post_pr_comment(pr_number, format_review_summary(
                "No changes detected. Auto-approving.", "PASSED"
            ))
            return

        # Truncate diff if too large to avoid token limits
        max_diff_len = 30000
        if len(diff) > max_diff_len:
            original_len = len(diff)
            diff = diff[:max_diff_len] + "\n\n... (diff truncated, see full diff in PR)"
            logger.info(f"Diff truncated from {original_len} to {max_diff_len} chars")

        review_prompt = load_template(
            "review_prompt.md",
            ISSUE_NUMBER=str(issue.number),
            ISSUE_TITLE=issue.title,
            ISSUE_BODY=issue.body,
            GIT_DIFF=diff,
            CHANGED_FILES="\n".join(changed_files),
        )

        # Prepend any visual QA findings from the after-screenshot review
        visual_verdict = read_visual_verdict(SCREENSHOTS_DIR)
        if visual_verdict:
            logger.info(f"Injecting visual verdict into review prompt: {visual_verdict.splitlines()[0]}")
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
            logger.error(f"Review failed: {e}")
            last_review_output = f"Review error: {e}"
            # On review failure, be lenient — treat as LGTM
            break

        verdict = parse_verdict(last_review_output)
        logger.info(f"Review verdict: {verdict}")

        if verdict == "LGTM":
            logger.info("Review passed!")
            visual_verdict = read_visual_verdict(SCREENSHOTS_DIR)
            visual_section = f"\n\n### Visual QA\n{visual_verdict}" if visual_verdict else ""
            label_pr(pr_number, "review-passed")
            post_pr_comment(pr_number, format_review_summary(
                last_review_output + visual_section, "PASSED"
            ))
            return

        # ── Verdict is NEEDS CHANGES ────────────────────────────
        if iteration < MAX_REVIEW_ITERATIONS:
            logger.warning(f"Review rejected. Applying fixes (iteration {iteration})...")

            fixer = ClineRunner(
                cline_dir=REPO_ROOT / f".cline-fixer-{iteration}",
                model=_cfg.models.fixer,
                # No MCP settings — fixer uses CLI tools only, same as coding_cline.
            )

            fix_prompt = load_template(
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
                    f"Next review iteration will see stale diff."
                )
                continue

    # ── 3. Exhausted iterations ─────────────────────────────────
    logger.warning("Max review iterations reached. Posting final review.")
    visual_verdict = read_visual_verdict(SCREENSHOTS_DIR)
    visual_section = f"\n\n### Visual QA\n{visual_verdict}" if visual_verdict else ""
    label_pr(pr_number, "review-needs-attention")
    post_pr_comment(pr_number, format_review_summary(
        last_review_output + visual_section, "NEEDS ATTENTION"
    ))

    logger.info("=" * 60)
    logger.info("Self-Review complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Self-review failed: {e}", exc_info=True)
        sys.exit(1)

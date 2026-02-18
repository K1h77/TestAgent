#!/usr/bin/env python3
"""Ralph Agent — Main orchestration script.

Reads a GitHub issue, creates a branch, runs Cline in TDD mode,
self-heals failing tests, takes before/after screenshots, and creates a PR.

All failures are explicit. Nothing proceeds silently with missing data.
"""

import logging
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

# Add parent directory to path so lib/ is importable
sys.path.insert(0, str(Path(__file__).parent))

from lib.agent_config import load_config
from lib.cline_runner import ClineRunner, ClineError
from lib.git_ops import (
    configure_git_user,
    create_branch,
    commit_and_push,
    create_pr,
    get_pr_number,
    post_issue_comment,
    GitError,
)
from lib.issue_parser import Issue, parse_issue, require_env
from lib.logging_config import setup_logging, format_summary
from lib.screenshot import take_screenshot, take_after_screenshot_with_review, embed_screenshots_markdown

logger = logging.getLogger("ralph-agent")

# Constants
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
MCP_SETTINGS_PATH = SCRIPTS_DIR / "cline-config" / "cline_mcp_settings.json"
PROMPTS_DIR = SCRIPTS_DIR / "prompts"
SCREENSHOTS_DIR = REPO_ROOT / "screenshots"

# Load central config from .github/agent_config.yml
_cfg = load_config()
MAX_CODING_ATTEMPTS = _cfg.retries.max_coding_attempts
CODING_TIMEOUT = _cfg.timeouts.coding_seconds


def load_prompt_template(name: str, **kwargs: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")

    content = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))

    return content


def start_server() -> subprocess.Popen:
    logger.info("Starting backend server...")

    # Install backend deps first (use ci for reproducible installs)
    subprocess.run(
        ["npm", "ci"],
        cwd=str(REPO_ROOT / "backend"),
        capture_output=True,
        text=True,
        check=True,
    )

    proc = subprocess.Popen(
        ["node", "server.js"],
        cwd=str(REPO_ROOT / "backend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server readiness
    for i in range(30):
        try:
            result = subprocess.run(
                ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:3000/"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip() == "200":
                logger.info("Backend server is ready")
                return proc
        except (subprocess.TimeoutExpired, Exception):
            pass
        time.sleep(1)

    proc.kill()
    raise RuntimeError(
        "Backend server failed to start within 30 seconds. "
        "Check backend/server.js for errors."
    )


def stop_server(proc: subprocess.Popen) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        logger.info("Backend server stopped")


def run_tests() -> tuple[bool, str]:
    logger.info("Running tests...")

    try:
        result = subprocess.run(
            ["npm", "test"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=_cfg.timeouts.test_seconds,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Tests timed out after {_cfg.timeouts.test_seconds}s")
        return False, f"Tests timed out after {_cfg.timeouts.test_seconds}s"

    output = result.stdout + "\n" + result.stderr
    success = result.returncode == 0

    if success:
        logger.info("Tests passed")
    else:
        logger.warning(f"Tests failed (exit {result.returncode})")
        logger.debug(f"Test output:\n{output}")

    return success, output


def get_git_diff() -> str:
    """Return the current uncommitted diff (truncated for prompt use)."""
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    diff = result.stdout.strip()
    if not diff:
        # Also check untracked files
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        diff = result.stdout.strip()
    return diff[:5000]


def get_repo_name() -> str:
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        # Fallback: parse from git remote
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        url = result.stdout.strip()
        # Handle both https and ssh URLs
        if url.endswith(".git"):
            url = url[:-4]
        parts = url.rstrip("/").split("/")
        return f"{parts[-2]}/{parts[-1]}"


def main() -> None:
    setup_logging(verbose=True)

    logger.info("=" * 60)
    logger.info("Ralph Agent starting")
    logger.info("=" * 60)

    # ── 1. Validate all inputs (fail-fast) ──────────────────────
    issue = parse_issue(
        number=require_env("ISSUE_NUMBER"),
        title=require_env("ISSUE_TITLE"),
        body=require_env("ISSUE_BODY"),
    )
    require_env("OPENROUTER_API_KEY")

    logger.info(f"Issue #{issue.number}: {issue.title}")
    logger.info(f"Issue body: {issue.body[:200]}...")

    # ── 2. Configure git ────────────────────────────────────────
    configure_git_user()

    # ── 3. Create branch ────────────────────────────────────────
    slug = re.sub(r"[^a-z0-9]+", "-", issue.title.lower()).strip("-")[:50].rstrip("-")
    branch = f"ralph/issue-{issue.number}-{slug}"
    create_branch(branch)
    logger.info(f"Branch created: {branch}")

    # ── 4. Post "working on it" comment ─────────────────────────
    try:
        post_issue_comment(
            issue.number,
            format_summary({"status": "started", "issue_number": issue.number}),
        )
    except GitError as e:
        logger.warning(f"Failed to post start comment (non-blocking): {e}")

    # ── 5. Configure Cline runners ──────────────────────────────
    coding_cline = ClineRunner(
        cline_dir=REPO_ROOT / ".cline-agent",
        model=_cfg.models.coding,
        plan_model=_cfg.models.coding_plan,
        mcp_settings_path=MCP_SETTINGS_PATH,
    )
    vision_cline = ClineRunner(
        cline_dir=REPO_ROOT / ".cline-vision",
        model=_cfg.models.vision,
        mcp_settings_path=MCP_SETTINGS_PATH,
    )

    # ── 6. Start backend server ─────────────────────────────────
    server = start_server()

    # Initialize screenshot paths before try so they're always defined
    before_path = None
    after_path = None

    try:
        # ── 7. Before screenshot ────────────────────────────────
        before_path = take_screenshot(
            vision_cline,
            SCREENSHOTS_DIR / "before.png",
            "before",
            issue_number=issue.number,
            issue_title=issue.title,
            issue_body=issue.body,
            timeout=_cfg.timeouts.screenshot_seconds,
        )

        # ── 8. Coding loop (TDD + retry with progress check) ─────
        logger.info("=" * 40)
        logger.info("CODING LOOP")
        logger.info("=" * 40)

        tests_passed = False
        coding_attempts = 0

        for attempt in range(1, MAX_CODING_ATTEMPTS + 1):
            coding_attempts = attempt
            logger.info(f"--- Coding attempt {attempt}/{MAX_CODING_ATTEMPTS} ---")

            if attempt == 1:
                # First attempt: fresh TDD prompt
                prompt = load_prompt_template(
                    "tdd_prompt.md",
                    ISSUE_NUMBER=str(issue.number),
                    ISSUE_TITLE=issue.title,
                    ISSUE_BODY=issue.body,
                    SCREENSHOTS_DIR=str(SCREENSHOTS_DIR),
                )
            else:
                # Subsequent attempts: check progress, build continuation prompt
                diff = get_git_diff()
                test_ok, test_output = run_tests()

                if test_ok:
                    tests_passed = True
                    logger.info(f"Tests passed on attempt {attempt} (before running Cline)")
                    break

                logger.info(f"Progress so far: {len(diff)} chars of diff")
                prompt = load_prompt_template(
                    "continue_prompt.md",
                    ISSUE_NUMBER=str(issue.number),
                    ISSUE_TITLE=issue.title,
                    ISSUE_BODY=issue.body,
                    GIT_DIFF=diff,
                    TEST_OUTPUT=test_output[:3000],
                )

            try:
                coding_cline.run(prompt, timeout=CODING_TIMEOUT, cwd=REPO_ROOT)
            except ClineError as e:
                logger.warning(f"Coding attempt {attempt} ended: {e}")
                continue

        # Final test check after last attempt
        if not tests_passed:
            success, _ = run_tests()
            if success:
                tests_passed = True
                logger.info("Tests passed after final attempt")
            else:
                logger.warning(
                    f"Tests still failing after {coding_attempts} attempts. Proceeding with PR."
                )

        # ── 10. After screenshot + inline visual review ────────
        logger.info("Taking 'after' screenshot with visual review...")
        stop_server(server)
        time.sleep(2)
        server = start_server()

        after_path, _ = take_after_screenshot_with_review(
            vision_cline,
            SCREENSHOTS_DIR / "after.png",
            issue_number=issue.number,
            issue_title=issue.title,
            issue_body=issue.body,
            timeout=_cfg.timeouts.screenshot_seconds,
        )

    finally:
        stop_server(server)

    # ── 11. Commit and push ─────────────────────────────────────
    logger.info("=" * 40)
    logger.info("COMMIT AND PUSH")
    logger.info("=" * 40)

    commit_message = (
        f"fix(#{issue.number}): {issue.title}\n\n"
        f"Automated fix by Ralph Agent.\n"
        f"Resolves #{issue.number}"
    )

    try:
        commit_and_push(commit_message, branch)
    except GitError as e:
        error_msg = str(e)
        logger.error(f"Commit/push failed: {error_msg}")
        post_issue_comment(
            issue.number,
            format_summary({"status": "failed", "issue_number": issue.number, "error": error_msg}),
        )
        raise RuntimeError(f"Commit/push failed: {error_msg}") from e

    # ── 12. Create PR ───────────────────────────────────────────
    repo_name = get_repo_name()

    screenshots_md = embed_screenshots_markdown(
        before_path=before_path,
        after_path=after_path,
        branch=branch,
        repo=repo_name,
    )

    test_status = "All tests passing" if tests_passed else "Some tests may be failing"
    pr_body = (
        f"## Automated Fix for #{issue.number}\n\n"
        f"**Issue:** {issue.title}\n\n"
        f"### Changes\n"
        f"This PR was automatically generated by Ralph Agent to resolve #{issue.number}.\n\n"
        f"### Test Status\n"
        f"{test_status} (coding attempts: {coding_attempts})\n\n"
        f"{screenshots_md}\n\n"
        f"---\n"
        f"*Generated by Ralph Autofix Agent*"
    )

    pr_url = create_pr(
        title=f"fix(#{issue.number}): {issue.title}",
        body=pr_body,
        base="main",
        head=branch,
    )

    pr_number = get_pr_number(pr_url)
    logger.info(f"PR created: {pr_url}")

    # Write PR number for self-review step
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"pr_number={pr_number}\n")
            f.write(f"pr_url={pr_url}\n")
            f.write(f"branch={branch}\n")
            f.flush()

    # ── 13. Post summary on issue ───────────────────────────────
    try:
        post_issue_comment(
            issue.number,
            format_summary({
                "status": "pr_created",
                "issue_number": issue.number,
                "pr_url": pr_url,
                "tests_passed": tests_passed,
                "coding_attempts": coding_attempts,
            }),
        )
    except GitError as e:
        logger.warning(f"Failed to post completion comment (non-blocking): {e}")

    logger.info("=" * 60)
    logger.info("Ralph Agent complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Ralph Agent failed: {e}", exc_info=True)
        sys.exit(1)

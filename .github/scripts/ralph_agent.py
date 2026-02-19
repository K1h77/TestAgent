#!/usr/bin/env python3
import logging
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.agent_config import load_config
from lib.cline_runner import ClineRunner, ClineError, get_openrouter_usage
from lib.utils import (
    get_git_diff,
    get_frontend_diff,
    get_repo_name,
    load_prompt_template,
    run_tests,
    start_server,
    stop_server,
)
from lib.git_ops import (
    configure_git_user,
    create_branch,
    commit_and_push,
    create_pr,
    get_pr_number,
    post_issue_comment,
    GitError,
)
from lib.issue_parser import parse_issue, require_env
from lib.logging_config import setup_logging, format_summary
from lib.screenshot import take_after_screenshot_with_review, embed_screenshots_markdown

logger = logging.getLogger("ralph-agent")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
MCP_SETTINGS_PATH = SCRIPTS_DIR / "cline-config" / "cline_mcp_settings.json"
PROMPTS_DIR = SCRIPTS_DIR / "prompts"
SCREENSHOTS_DIR = REPO_ROOT / "screenshots"

_cfg = load_config()
MAX_CODING_ATTEMPTS = _cfg.retries.max_coding_attempts
CODING_TIMEOUT = _cfg.timeouts.coding_seconds


def validate_inputs():
    issue = parse_issue(
        number=require_env("ISSUE_NUMBER"),
        title=require_env("ISSUE_TITLE"),
        body=require_env("ISSUE_BODY"),
        labels=os.environ.get("ISSUE_LABELS", ""),
    )
    require_env("OPENROUTER_API_KEY")

    logger.info(f"Issue #{issue.number}: {issue.title}")
    logger.info(f"Issue body: {issue.body[:200]}...")
    logger.info(f"Issue labels: {sorted(issue.labels) or '(none)'}")
    logger.info(f"Frontend checks enabled: {issue.is_frontend()}")
    return issue


def setup_git_branch(issue) -> str:
    configure_git_user()

    slug = re.sub(r"[^a-z0-9]+", "-", issue.title.lower()).strip("-")[:50].rstrip("-")
    desired_branch = f"ralph/issue-{issue.number}-{slug}"
    branch = create_branch(desired_branch)
    logger.info(f"Branch created: {branch}")
    return branch


def post_start_comment(issue) -> None:
    try:
        post_issue_comment(
            issue.number,
            format_summary({"status": "started", "issue_number": issue.number}),
        )
    except GitError as e:
        logger.warning(f"Failed to post start comment (non-blocking): {e}")


def configure_runners(issue):
    is_hard = "hard" in issue.labels
    logger.info(f"Issue labelled hard: {is_hard}")

    default_cline = ClineRunner(
        cline_dir=REPO_ROOT / ".cline-agent-default",
        model=_cfg.models.coder_default,
        plan_model=_cfg.models.planner_default,
    )
    hard_cline = ClineRunner(
        cline_dir=REPO_ROOT / ".cline-agent-hard",
        model=_cfg.models.coder_hard,
        plan_model=_cfg.models.planner_hard,
    )
    vision_cline = (
        ClineRunner(
            cline_dir=REPO_ROOT / ".cline-vision",
            model=_cfg.models.vision,
            mcp_settings_path=MCP_SETTINGS_PATH,
        )
        if issue.is_frontend()
        else None
    )
    return is_hard, default_cline, hard_cline, vision_cline


def start_server_if_frontend_issue(issue):
    if issue.is_frontend():
        return start_server(REPO_ROOT)
    logger.info("Skipping server start and screenshots (not a frontend issue)")
    return None


def coding_loop(issue, is_hard, default_cline, hard_cline) -> tuple[bool, int]:
    logger.info("=" * 40)
    logger.info("CODING LOOP")
    logger.info("=" * 40)

    tests_passed = False
    coding_attempts = 0

    for attempt in range(1, MAX_CODING_ATTEMPTS + 1):
        coding_attempts = attempt
        is_final = attempt == MAX_CODING_ATTEMPTS

        use_hard = is_hard or is_final
        coding_cline = hard_cline if use_hard else default_cline
        active_planner = _cfg.models.planner_hard if use_hard else _cfg.models.planner_default
        active_coder = _cfg.models.coder_hard if use_hard else _cfg.models.coder_default
        logger.info(
            f"--- Coding attempt {attempt}/{MAX_CODING_ATTEMPTS} "
            f"[planner: {active_planner} | coder: {active_coder}]"
            + (" (hard runner — hard ticket)" if is_hard else "")
            + (" (hard runner — final attempt)" if not is_hard and is_final else "")
            + " ---"
        )

        if attempt == 1:
            prompt = load_prompt_template(
                PROMPTS_DIR,
                "tdd_prompt.md",
                ISSUE_NUMBER=str(issue.number),
                ISSUE_TITLE=issue.title,
                ISSUE_BODY=issue.body,
                SCREENSHOTS_DIR=str(SCREENSHOTS_DIR),
            )
        else:
            diff = get_git_diff(REPO_ROOT)
            test_ok, test_output = run_tests(REPO_ROOT, _cfg.timeouts.test_seconds)

            if test_ok:
                tests_passed = True
                logger.info(f"Tests passed on attempt {attempt} (before running Cline)")
                break

            logger.info(f"Prior diff to audit: {len(diff)} chars")
            prompt = load_prompt_template(
                PROMPTS_DIR,
                "escalate_prompt.md",
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

    if not tests_passed:
        success, _ = run_tests(REPO_ROOT, _cfg.timeouts.test_seconds)
        if success:
            tests_passed = True
            logger.info("Tests passed after final attempt")
        else:
            logger.warning(
                f"Tests still failing after {coding_attempts} attempts. Proceeding with PR."
            )

    return tests_passed, coding_attempts


def take_after_screenshots(issue, vision_cline, server):
    after_paths: list = []

    if not (issue.is_frontend() and vision_cline is not None and server is not None):
        return after_paths, server

    logger.info("Taking 'after' screenshots with visual review...")
    stop_server(server)
    time.sleep(2)
    server = start_server(REPO_ROOT)

    frontend_diff = get_frontend_diff(REPO_ROOT)
    logger.info(f"Frontend diff for visual review: {len(frontend_diff)} chars")

    after_paths, _ = take_after_screenshot_with_review(
        vision_cline,
        SCREENSHOTS_DIR / "after.png",
        issue_number=issue.number,
        issue_title=issue.title,
        issue_body=issue.body,
        frontend_diff=frontend_diff,
        timeout=_cfg.timeouts.screenshot_seconds,
    )
    return after_paths, server


def commit_changes(issue, branch) -> None:
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


def build_and_create_pr(
    issue, branch, tests_passed, coding_attempts, before_path, after_paths, cost_baseline
) -> tuple[str, str]:
    repo_name = get_repo_name()

    cost_final = get_openrouter_usage()
    if cost_final is not None and cost_baseline is not None:
        total_cost = max(0.0, cost_final - cost_baseline)
        cost_section = f"### Token Cost\n${total_cost:.4f} USD (via OpenRouter)\n\n"
        logger.info(f"Total PR cost: ${total_cost:.4f} USD")
    else:
        cost_section = ""

    screenshots_md = embed_screenshots_markdown(
        before_path=before_path,
        after_paths=after_paths,
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
        f"{cost_section}"
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

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"pr_number={pr_number}\n")
            f.write(f"pr_url={pr_url}\n")
            f.write(f"branch={branch}\n")
            f.flush()

    return pr_url, pr_number


def post_completion_comment(issue, pr_url, tests_passed, coding_attempts) -> None:
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


def main() -> None:
    setup_logging(verbose=True)
    logger.info("=" * 60)
    logger.info("Ralph Agent starting")
    logger.info("=" * 60)

    cost_baseline = get_openrouter_usage()

    issue                                    = validate_inputs()
    branch                                   = setup_git_branch(issue)
    post_start_comment(issue)
    is_hard, default_cline, hard_cline, vision_cline = configure_runners(issue)
    server                                   = start_server_if_frontend_issue(issue)

    before_path = None
    after_paths: list = []

    try:
        tests_passed, coding_attempts = coding_loop(issue, is_hard, default_cline, hard_cline)
        after_paths, server           = take_after_screenshots(issue, vision_cline, server)
    finally:
        if server is not None:
            stop_server(server)

    commit_changes(issue, branch)
    pr_url, _ = build_and_create_pr(
        issue, branch, tests_passed, coding_attempts, before_path, after_paths, cost_baseline
    )
    post_completion_comment(issue, pr_url, tests_passed, coding_attempts)

    logger.info("=" * 60)
    logger.info("Ralph Agent complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Ralph Agent failed: {e}", exc_info=True)
        sys.exit(1)

"""Structured logging setup for Ralph Agent.

Provides verbose logging to stdout (for workflow logs) and a separate
format_summary() function for concise markdown summaries posted to
issue comments and PR bodies.
"""

import logging
import sys
from datetime import datetime, timezone


class WorkflowFormatter(logging.Formatter):
    """Formatter that produces verbose, timestamped output for GitHub Actions logs."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        level = record.levelname.ljust(7)
        return f"[{record.name}] {timestamp} {level} {record.getMessage()}"


def setup_logging(verbose: bool = True) -> None:
    """Configure root logger for workflow output.

    Args:
        verbose: If True, set level to DEBUG. Otherwise INFO.
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Remove existing handlers to avoid duplicates
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(WorkflowFormatter())
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    root.addHandler(handler)


def format_summary(details: dict) -> str:
    """Format a concise markdown summary for issue/PR comments.

    Args:
        details: Dictionary with keys like 'status', 'issue_number',
                 'pr_url', 'tests_passed', 'heal_attempts', 'error'.

    Returns:
        Concise markdown string suitable for GitHub comments.
    """
    lines = []

    status = details.get("status", "unknown")
    issue_number = details.get("issue_number", "?")

    if status == "started":
        lines.append(f"**Ralph Agent** is working on issue #{issue_number}...")
        lines.append("")
        lines.append("I'll create a PR when the fix is ready.")
    elif status == "pr_created":
        pr_url = details.get("pr_url", "")
        tests_passed = details.get("tests_passed", False)
        heal_attempts = details.get("heal_attempts", 0)
        lines.append(f"**Ralph Agent** has created a fix: {pr_url}")
        lines.append("")
        test_status = "passing" if tests_passed else "partially passing"
        lines.append(f"- Tests: {test_status}")
        if heal_attempts > 1:
            lines.append(f"- Self-healing attempts: {heal_attempts}")
    elif status == "failed":
        error = details.get("error", "Unknown error")
        lines.append(f"**Ralph Agent** failed to fix issue #{issue_number}.")
        lines.append("")
        lines.append(f"Error: {error}")
    else:
        lines.append(f"**Ralph Agent** — status: {status}")

    return "\n".join(lines)


def format_review_summary(review_output: str, verdict: str) -> str:
    """Format review output as a concise PR comment.

    Args:
        review_output: Full review output from Cline.
        verdict: "PASSED" or "NEEDS ATTENTION".

    Returns:
        Markdown string for PR comment.
    """
    lines = [
        f"## Ralph Self-Review — {verdict}",
        "",
        "This review was performed by a **separate AI instance** with fresh context.",
        "",
        "---",
        "",
    ]

    # Truncate review output to keep comment concise
    max_len = 3000
    if len(review_output) > max_len:
        review_output = review_output[:max_len] + "\n\n... (truncated, see workflow logs for full output)"

    lines.append(review_output)
    lines.append("")
    lines.append("---")
    lines.append("*Automated review by Ralph Agent*")

    return "\n".join(lines)

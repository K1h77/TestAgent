"""Git operations with explicit error handling.

Every operation raises on failure — nothing is silently ignored.
Uses subprocess to call git and gh CLI directly.
"""

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class GitError(Exception):
    """Raised when a git or gh CLI operation fails."""

    def __init__(self, message: str, stderr: str = "", exit_code: int = -1):
        super().__init__(message)
        self.stderr = stderr
        self.exit_code = exit_code


def _run_git(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command and return the result.

    Args:
        args: Git command arguments (without 'git' prefix).
        check: If True, raise GitError on non-zero exit.

    Returns:
        CompletedProcess result.

    Raises:
        GitError: If the command fails and check is True.
    """
    cmd = ["git"] + args
    logger.debug(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if check and result.returncode != 0:
        logger.error(f"Git command failed: {' '.join(cmd)}")
        logger.error(f"stderr: {result.stderr}")
        raise GitError(
            f"git {' '.join(args)} failed (exit {result.returncode}): {result.stderr.strip()}",
            stderr=result.stderr,
            exit_code=result.returncode,
        )

    return result


def _run_gh(args: list[str]) -> subprocess.CompletedProcess:
    """Run a gh CLI command and return the result.

    Args:
        args: gh command arguments (without 'gh' prefix).

    Returns:
        CompletedProcess result.

    Raises:
        GitError: If the command fails.
    """
    cmd = ["gh"] + args
    logger.debug(f"Running: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"gh command failed: {' '.join(cmd)}")
        logger.error(f"stderr: {result.stderr}")
        raise GitError(
            f"gh {' '.join(args)} failed (exit {result.returncode}): {result.stderr.strip()}",
            stderr=result.stderr,
            exit_code=result.returncode,
        )

    return result


def configure_git_user(name: str = "Ralph Bot", email: str = "ralph-bot@users.noreply.github.com") -> None:
    """Configure git user for commits.

    Args:
        name: Git user name.
        email: Git user email.
    """
    _run_git(["config", "user.name", name])
    _run_git(["config", "user.email", email])
    logger.info(f"Git user configured: {name} <{email}>")


def create_branch(name: str) -> None:
    """Create and checkout a new branch from current HEAD.

    If the branch already exists on the remote (e.g. from a prior cancelled
    run), checks it out and resets it to the remote state instead of failing.

    Args:
        name: Branch name.

    Raises:
        GitError: If branch creation fails.
        ValueError: If name is empty.
    """
    if not name or not name.strip():
        raise ValueError("Branch name cannot be empty.")

    name = name.strip()

    # Fetch so we have up-to-date remote refs
    _run_git(["fetch", "origin"], check=False)

    # Check if the branch already exists on the remote
    ls = _run_git(["ls-remote", "--heads", "origin", name], check=False)
    if ls.stdout.strip():
        # Remote branch exists — reuse it, reset to remote state
        logger.warning(
            f"Branch '{name}' already exists on remote (prior run?). "
            f"Checking out and resetting to origin/{name}."
        )
        _run_git(["checkout", name])
        _run_git(["reset", "--hard", f"origin/{name}"])
    else:
        _run_git(["checkout", "-b", name])

    logger.info(f"On branch: {name}")


def commit_and_push(message: str, branch: str) -> None:
    """Stage all changes, commit, and push to origin.

    Args:
        message: Commit message.
        branch: Branch name to push.

    Raises:
        GitError: If there are no changes to commit, or if push fails.
        ValueError: If message or branch is empty.
    """
    if not message or not message.strip():
        raise ValueError("Commit message cannot be empty.")
    if not branch or not branch.strip():
        raise ValueError("Branch name cannot be empty.")

    # Stage all changes
    _run_git(["add", "-A"])

    # Safety check: abort if any secrets.json files are staged (API key leak guard)
    staged = _run_git(["diff", "--cached", "--name-only"])
    secret_files = [f for f in staged.stdout.splitlines() if "secrets.json" in f or "globalState.json" in f]
    if secret_files:
        _run_git(["reset", "HEAD"] + secret_files)  # unstage them
        logger.error(
            f"SECURITY: Attempted to commit files that may contain secrets: {secret_files}. "
            "They have been unstaged. Add the .cline-*/ directories to .gitignore."
        )
        raise GitError(
            f"Aborting commit: sensitive files were staged: {secret_files}. "
            "Check that .cline-*/ is in .gitignore."
        )

    # Check if there are actually changes to commit
    status = _run_git(["status", "--porcelain"])
    if not status.stdout.strip():
        raise GitError(
            "No changes to commit. The agent may not have produced any code changes."
        )

    # Commit
    _run_git(["commit", "-m", message])
    logger.info(f"Committed: {message[:80]}")

    # Push — retry once with pull-rebase on non-fast-forward rejection
    push_result = _run_git(["push", "origin", branch.strip()], check=False)
    if push_result.returncode != 0:
        stderr = push_result.stderr
        if "non-fast-forward" in stderr or "rejected" in stderr:
            logger.warning(
                "Push rejected (non-fast-forward). Attempting pull-rebase and retry..."
            )
            _run_git(["pull", "--rebase", "origin", branch.strip()])
            _run_git(["push", "origin", branch.strip()])
        else:
            raise GitError(
                f"git push origin {branch.strip()} failed (exit {push_result.returncode}): "
                f"{stderr.strip()}",
                stderr=stderr,
                exit_code=push_result.returncode,
            )
    logger.info(f"Pushed to origin/{branch}")


def create_pr(title: str, body: str, base: str, head: str) -> str:
    """Create a pull request via gh CLI.

    Args:
        title: PR title.
        body: PR body (markdown).
        base: Base branch (e.g., 'main').
        head: Head branch (e.g., 'ralph/issue-42').

    Returns:
        PR URL.

    Raises:
        GitError: If PR creation fails.
        ValueError: If required fields are empty.
    """
    if not title or not title.strip():
        raise ValueError("PR title cannot be empty.")
    if not head or not head.strip():
        raise ValueError("PR head branch cannot be empty.")

    result = _run_gh([
        "pr", "create",
        "--title", title.strip(),
        "--body", body,
        "--base", base.strip(),
        "--head", head.strip(),
    ])

    pr_url = result.stdout.strip()
    if not pr_url:
        raise GitError("gh pr create succeeded but returned no URL.")

    logger.info(f"PR created: {pr_url}")
    return pr_url


def get_pr_number(pr_url: str) -> str:
    """Extract PR number from a GitHub PR URL.

    Args:
        pr_url: Full PR URL (e.g., https://github.com/user/repo/pull/42).

    Returns:
        PR number as string.
    """
    parts = pr_url.rstrip("/").split("/")
    return parts[-1]


def get_diff(base: str = "main") -> str:
    """Get the diff between base branch and HEAD.

    Args:
        base: Base branch to diff against.

    Returns:
        Diff string.
    """
    result = _run_git(["diff", f"{base}...HEAD"])
    return result.stdout


def get_changed_files(base: str = "main") -> list[str]:
    """Get list of files changed between base and HEAD.

    Args:
        base: Base branch to diff against.

    Returns:
        List of changed file paths.
    """
    result = _run_git(["diff", f"{base}...HEAD", "--name-only"])
    files = [f for f in result.stdout.strip().splitlines() if f.strip()]
    logger.info(f"Changed files: {len(files)}")
    return files


def post_issue_comment(issue_number: int, body: str) -> None:
    """Post a comment on a GitHub issue.

    Args:
        issue_number: Issue number.
        body: Comment body (markdown).

    Raises:
        GitError: If comment posting fails.
    """
    _run_gh(["issue", "comment", str(issue_number), "--body", body])
    logger.info(f"Posted comment on issue #{issue_number}")


def post_pr_comment(pr_number: str, body: str) -> None:
    """Post a comment on a GitHub PR.

    Args:
        pr_number: PR number.
        body: Comment body (markdown).

    Raises:
        GitError: If comment posting fails.
    """
    _run_gh(["pr", "comment", pr_number, "--body", body])
    logger.info(f"Posted comment on PR #{pr_number}")


def label_pr(pr_number: str, label: str) -> None:
    """Add a label to a PR.

    Args:
        pr_number: PR number.
        label: Label name.

    Raises:
        GitError: If labeling fails.
    """
    _run_gh(["pr", "edit", pr_number, "--add-label", label])
    logger.info(f"Added label '{label}' to PR #{pr_number}")

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("ralph-agent")


def get_git_diff(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    diff = result.stdout.strip()
    if not diff:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_root),
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
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        url = result.stdout.strip()
        if url.endswith(".git"):
            url = url[:-4]
        parts = url.rstrip("/").split("/")
        return f"{parts[-2]}/{parts[-1]}"

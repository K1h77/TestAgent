import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ralph-agent")

_FRONTEND_GLOBS = ["*.html", "*.css", "*.js", "*.jsx", "*.ts", "*.tsx", "*.vue", "*.svelte"]


def start_server(repo_root: Path) -> subprocess.Popen:
    logger.info("Starting backend server...")

    subprocess.run(
        ["npm", "ci"],
        cwd=str(repo_root / "backend"),
        capture_output=True,
        text=True,
        check=True,
    )

    proc = subprocess.Popen(
        ["node", "server.js"],
        cwd=str(repo_root / "backend"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    for _ in range(30):
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


def run_tests(repo_root: Path, test_timeout: int) -> tuple[bool, str]:
    logger.info("Running tests...")

    try:
        result = subprocess.run(
            ["npm", "test"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=test_timeout,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"Tests timed out after {test_timeout}s")
        return False, f"Tests timed out after {test_timeout}s"

    output = result.stdout + "\n" + result.stderr
    success = result.returncode == 0

    if success:
        logger.info("Tests passed")
    else:
        logger.warning(f"Tests failed (exit {result.returncode})")
        logger.debug(f"Test output:\n{output}")

    return success, output


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


def get_frontend_diff(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "diff", "main..HEAD", "--", *_FRONTEND_GLOBS],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=30,
    )
    diff = result.stdout.strip()
    if not diff:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", *_FRONTEND_GLOBS],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        diff = result.stdout.strip()
    return diff


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


def load_prompt_template(prompts_dir: Path, name: str, **kwargs: str) -> str:
    path = prompts_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")

    content = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))

    return content


def screenshot_relative_path(path: Path) -> str:
    parts = Path(path).parts
    for i, part in enumerate(parts):
        if part == "screenshots":
            return "/".join(parts[i:])
    return Path(path).name


def embed_screenshots_markdown(
    before_path: Optional[Path],
    after_paths: list,
    branch: str,
    repo: str,
) -> str:
    lines = ["### Screenshots", ""]

    if before_path is None and not after_paths:
        lines.append("*No screenshots captured.*")
        return "\n".join(lines)

    base_url = f"https://raw.githubusercontent.com/{repo}/{branch}"

    if before_path is not None:
        relative = screenshot_relative_path(before_path)
        lines.append("**Before:**")
        lines.append(f"![Before]({base_url}/{relative})")
        lines.append("")

    if after_paths:
        lines.append("**After:**")
        for i, p in enumerate(after_paths, 1):
            relative = screenshot_relative_path(p)
            label = f"After {i}" if len(after_paths) > 1 else "After"
            lines.append(f"![{label}]({base_url}/{relative})")
        lines.append("")

    return "\n".join(lines)


def read_visual_verdict(screenshots_dir: Path) -> Optional[str]:
    verdict_path = Path(screenshots_dir) / "visual_verdict.txt"
    if not verdict_path.exists():
        return None
    content = verdict_path.read_text(encoding="utf-8").strip()
    return content if content else None

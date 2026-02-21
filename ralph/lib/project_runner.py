"""Project-specific runner utilities.

Provides run_tests, start_server, stop_server, and get_frontend_diff.
All values (test command, server config) come from agent_config.yml via
the ServerConfig/ProjectConfig dataclasses — nothing is hardcoded here.
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ralph.lib.agent_config import ServerConfig

logger = logging.getLogger("ralph-agent")

_FRONTEND_GLOBS = [
    "*.html",
    "*.css",
    "*.js",
    "*.jsx",
    "*.ts",
    "*.tsx",
    "*.vue",
    "*.svelte",
]


def run_tests(repo_root: Path, test_timeout: int, test_command: str = "npm test") -> tuple[bool, str]:
    """Run the project test suite.

    Args:
        repo_root: Repository root directory.
        test_timeout: Maximum seconds to wait for tests.
        test_command: Shell command to run tests (e.g. "npm test", "pytest").

    Returns:
        Tuple of (success: bool, output: str).
    """
    logger.info(f"Running tests: {test_command}")

    try:
        result = subprocess.run(
            test_command.split(),
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


def start_server(repo_root: Path, server_cfg: "ServerConfig") -> subprocess.Popen:
    """Start the project's development server.

    Args:
        repo_root: Repository root directory.
        server_cfg: ServerConfig from agent_config.yml.

    Returns:
        Running server subprocess.

    Raises:
        RuntimeError: If server does not start within 30 seconds.
    """
    logger.info("Starting backend server...")

    subprocess.run(
        server_cfg.install_command.split(),
        cwd=str(repo_root / server_cfg.working_dir),
        capture_output=True,
        text=True,
        check=True,
    )

    proc = subprocess.Popen(
        server_cfg.start_command.split(),
        cwd=str(repo_root / server_cfg.working_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    url = f"http://localhost:{server_cfg.port}{server_cfg.health_path}"
    for _ in range(30):
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-s",
                    "-o",
                    "/dev/null",
                    "-w",
                    "%{http_code}",
                    url,
                ],
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
        f"Backend server failed to start within 30 seconds. "
        f"Check {server_cfg.working_dir}/{server_cfg.start_command} for errors."
    )


def stop_server(proc: subprocess.Popen) -> None:
    """Stop a running server process.

    Args:
        proc: Server subprocess to stop.
    """
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        logger.info("Backend server stopped")


def get_frontend_diff(repo_root: Path, base_branch: str = "main") -> str:
    """Get git diff for frontend files only.

    Args:
        repo_root: Repository root directory.
        base_branch: Base branch to diff against.

    Returns:
        Diff string for frontend file changes.
    """
    result = subprocess.run(
        ["git", "diff", f"{base_branch}..HEAD", "--", *_FRONTEND_GLOBS],
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

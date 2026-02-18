"""Cline CLI wrapper with subprocess management, output capture, and error handling.

Provides a clean interface to invoke Cline in YOLO mode with configurable
models, MCP settings, and command permissions. All failures are raised
explicitly — never silently swallowed.
"""

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ClineError(Exception):
    """Raised when a Cline CLI invocation fails."""

    def __init__(self, message: str, stdout: str = "", stderr: str = "", exit_code: int = -1):
        super().__init__(message)
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code


@dataclass(frozen=True)
class ClineResult:
    """Result of a Cline CLI invocation."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        return self.exit_code == 0


# Default permissions: allow dev-safe commands, block destructive ones
DEFAULT_COMMAND_PERMISSIONS = {
    "allow": [
        "npm *", "npx *", "node *", "git *",
        "cat *", "ls *", "mkdir *", "cd *", "echo *", "cp *", "mv *",
        "python *", "pip *", "pytest *",
    ],
    "deny": [
        "rm -rf /", "rm -rf /*", "shutdown *", "reboot *",
        "curl *|*sh", "wget *|*sh",
    ],
    "allowRedirects": True,
}

READ_ONLY_PERMISSIONS = {
    "allow": [
        "git diff *", "git log *", "git show *", "git status",
        "cat *", "ls *", "npm test", "npx jest *", "npx playwright *",
        "node *", "head *", "tail *", "wc *",
    ],
    "deny": [
        "rm *", "mv *", "cp *", "git push *", "git commit *",
        "git add *", "git checkout *", "git reset *",
        "npm install *", "pip install *",
    ],
    "allowRedirects": False,
}


class ClineRunner:
    """Manages Cline CLI invocations with isolated config directories."""

    def __init__(
        self,
        cline_dir: Path,
        model: str,
        mcp_settings_path: Optional[Path] = None,
        command_permissions: Optional[dict] = None,
    ):
        """Initialize the Cline runner.

        Args:
            cline_dir: Isolated directory for Cline's config/state.
            model: OpenRouter model ID (e.g., 'minimax/minimax-m2.5').
            mcp_settings_path: Path to cline_mcp_settings.json source file.
            command_permissions: Command permission dict. Defaults to DEFAULT_COMMAND_PERMISSIONS.

        Raises:
            FileNotFoundError: If cline binary is not found on PATH.
        """
        self.cline_dir = Path(cline_dir)
        self.model = model
        self.mcp_settings_path = mcp_settings_path
        self.command_permissions = command_permissions or DEFAULT_COMMAND_PERMISSIONS

        # Verify cline is installed
        if not shutil.which("cline"):
            raise FileNotFoundError(
                "Cline CLI is not installed or not on PATH. "
                "Install it with: npm install -g cline"
            )

        # Set up isolated config directory
        self._setup_cline_dir()

    def _setup_cline_dir(self) -> None:
        """Create and configure the isolated Cline directory."""
        self.cline_dir.mkdir(parents=True, exist_ok=True)

        # Copy MCP settings if provided
        if self.mcp_settings_path and self.mcp_settings_path.exists():
            dest = self.cline_dir / "cline_mcp_settings.json"
            if not dest.exists():
                import shutil as sh
                sh.copy2(self.mcp_settings_path, dest)
                logger.debug(f"Copied MCP settings to {dest}")

    def run(
        self,
        prompt: str,
        timeout: int = 600,
        cwd: Optional[Path] = None,
    ) -> ClineResult:
        """Run Cline CLI in YOLO mode with the given prompt.

        Args:
            prompt: The task prompt to send to Cline.
            timeout: Max execution time in seconds.
            cwd: Working directory for Cline. Defaults to current dir.

        Returns:
            ClineResult with stdout, stderr, and exit code.

        Raises:
            ClineError: If Cline fails or times out.
            ValueError: If prompt is empty.
        """
        if not prompt or not prompt.strip():
            raise ValueError("Cline prompt cannot be empty.")

        cmd = [
            "cline",
            "-y",
            "--model", self.model,
            "--timeout", str(timeout),
        ]

        if cwd:
            cmd.extend(["-c", str(cwd)])

        cmd.append(prompt)

        env = os.environ.copy()
        env["CLINE_DIR"] = str(self.cline_dir)
        env["CLINE_COMMAND_PERMISSIONS"] = json.dumps(self.command_permissions)

        logger.info(f"Running Cline (model={self.model}, timeout={timeout}s)")
        logger.debug(f"CLINE_DIR={self.cline_dir}")
        logger.debug(f"Prompt length: {len(prompt)} chars")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout + 30,  # Extra buffer for Cline's own timeout
                env=env,
                cwd=str(cwd) if cwd else None,
            )
        except subprocess.TimeoutExpired as e:
            logger.error(f"Cline timed out after {timeout}s")
            raise ClineError(
                f"Cline timed out after {timeout} seconds",
                stdout=e.stdout or "",
                stderr=e.stderr or "",
                exit_code=-1,
            ) from e
        except FileNotFoundError:
            raise ClineError(
                "Cline CLI binary not found. Is it installed globally?",
                exit_code=-1,
            )

        # Log full output at debug level (visible in workflow logs)
        if result.stdout:
            for line in result.stdout.splitlines():
                logger.debug(f"[cline stdout] {line}")
        if result.stderr:
            for line in result.stderr.splitlines():
                logger.debug(f"[cline stderr] {line}")

        logger.info(f"Cline finished (exit_code={result.returncode})")

        cline_result = ClineResult(
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
        )

        if not cline_result.success:
            logger.error(
                f"Cline failed with exit code {result.returncode}. "
                f"stderr: {result.stderr[:500]}"
            )
            raise ClineError(
                f"Cline exited with code {result.returncode}",
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )

        return cline_result

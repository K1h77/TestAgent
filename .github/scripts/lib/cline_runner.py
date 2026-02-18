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
        plan_model: Optional[str] = None,
        mcp_settings_path: Optional[Path] = None,
        command_permissions: Optional[dict] = None,
    ):
        """Initialize the Cline runner.

        Args:
            cline_dir: Isolated directory for Cline's config/state.
            model: OpenRouter model ID for act mode (e.g., 'minimax/minimax-m2.5').
            plan_model: OpenRouter model ID for plan mode. Defaults to model.
            mcp_settings_path: Path to cline_mcp_settings.json source file.
            command_permissions: Command permission dict. Defaults to DEFAULT_COMMAND_PERMISSIONS.

        Raises:
            FileNotFoundError: If cline binary is not found on PATH.
        """
        self.cline_dir = Path(cline_dir)
        self.model = model
        self.plan_model = plan_model or model
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
        data_dir = self.cline_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Copy MCP settings if provided
        if self.mcp_settings_path and self.mcp_settings_path.exists():
            dest = self.cline_dir / "cline_mcp_settings.json"
            if not dest.exists():
                import shutil as sh
                sh.copy2(self.mcp_settings_path, dest)
                logger.debug(f"Copied MCP settings to {dest}")

        # Write auth config so Cline doesn't prompt interactively
        global_state = data_dir / "globalState.json"
        if not global_state.exists():
            api_key = os.environ.get("OPENROUTER_API_KEY", "")
            state = {
                "welcomeViewCompleted": True,
                "actModeApiProvider": "openrouter",
                "actModeApiModelId": self.model,
                "planModeApiProvider": "openrouter",
                "planModeApiModelId": self.plan_model,
            }
            global_state.write_text(json.dumps(state, indent=2), encoding="utf-8")
            logger.debug(f"Wrote globalState.json to {global_state}")

            if api_key:
                secrets_file = data_dir / "secrets.json"
                secrets_file.write_text(
                    json.dumps({"openRouterApiKey": api_key}), encoding="utf-8"
                )
                logger.debug(f"Wrote secrets.json to {secrets_file}")

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

        stdout_lines = []
        stderr_lines = []
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(cwd) if cwd else None,
            )

            import select
            import time as _time

            deadline = _time.monotonic() + timeout + 30
            while proc.poll() is None:
                remaining = deadline - _time.monotonic()
                if remaining <= 0:
                    proc.kill()
                    raise subprocess.TimeoutExpired(cmd, timeout)

                # Read available output without blocking forever
                try:
                    # Try non-blocking reads with a short timeout
                    if proc.stdout and proc.stdout.readable():
                        line = proc.stdout.readline()
                        if line:
                            line = line.rstrip("\n")
                            stdout_lines.append(line)
                            logger.info(f"[cline] {line}")
                    if proc.stderr and proc.stderr.readable():
                        line = proc.stderr.readline()
                        if line:
                            line = line.rstrip("\n")
                            stderr_lines.append(line)
                            logger.info(f"[cline stderr] {line}")
                except Exception:
                    _time.sleep(0.1)

            # Read any remaining output after process exits
            if proc.stdout:
                for line in proc.stdout:
                    line = line.rstrip("\n")
                    stdout_lines.append(line)
                    logger.info(f"[cline] {line}")
            if proc.stderr:
                for line in proc.stderr:
                    line = line.rstrip("\n")
                    stderr_lines.append(line)
                    logger.info(f"[cline stderr] {line}")

            result_stdout = "\n".join(stdout_lines)
            result_stderr = "\n".join(stderr_lines)
            returncode = proc.returncode

        except subprocess.TimeoutExpired:
            logger.error(f"Cline timed out after {timeout}s")
            raise ClineError(
                f"Cline timed out after {timeout} seconds",
                stdout="\n".join(stdout_lines),
                stderr="\n".join(stderr_lines),
                exit_code=-1,
            )
        except FileNotFoundError:
            raise ClineError(
                "Cline CLI binary not found. Is it installed globally?",
                exit_code=-1,
            )

        logger.info(f"Cline finished (exit_code={returncode})")

        cline_result = ClineResult(
            stdout=result_stdout,
            stderr=result_stderr,
            exit_code=returncode,
        )

        if not cline_result.success:
            logger.error(
                f"Cline failed with exit code {returncode}. "
                f"stderr: {result_stderr[:500]}"
            )
            raise ClineError(
                f"Cline exited with code {returncode}",
                stdout=result_stdout,
                stderr=result_stderr,
                exit_code=returncode,
            )

        return cline_result

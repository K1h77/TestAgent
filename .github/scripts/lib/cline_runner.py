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
import threading
import time as _time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Patterns that indicate Cline is waiting for interactive input
_STUCK_PATTERNS = [
    "Do you want to proceed",
    "Press Enter",
    "(Y/n)",
    "(y/N)",
    "Approve?",
    "waiting for approval",
    "Please run 'cline auth'",
]


def get_openrouter_usage() -> Optional[float]:
    """Query OpenRouter API for current usage (credits consumed in USD).

    Returns the usage value, or None if the API call fails.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return None
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/key",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            return data.get("data", {}).get("usage")
    except Exception as e:
        logger.debug(f"OpenRouter usage check failed: {e}")
        return None


# Keep private alias for backward compatibility
_get_openrouter_usage = get_openrouter_usage


class ClineError(Exception):
    """Raised when a Cline CLI invocation fails."""

    def __init__(
        self, message: str, stdout: str = "", stderr: str = "", exit_code: int = -1
    ):
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
    cost_usd: Optional[float] = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0


# Default permissions: allow dev-safe commands, block destructive ones
DEFAULT_COMMAND_PERMISSIONS = {
    "allow": [
        "npm *",
        "npx *",
        "node *",
        "git *",
        "cat *",
        "ls *",
        "mkdir *",
        "cd *",
        "echo *",
        "cp *",
        "mv *",
        "python *",
        "pip *",
        "pytest *",
    ],
    "deny": [
        "rm -rf /",
        "rm -rf /*",
        "shutdown *",
        "reboot *",
        "curl *|*sh",
        "wget *|*sh",
    ],
    "allowRedirects": True,
}

READ_ONLY_PERMISSIONS = {
    "allow": [
        "git diff *",
        "git log *",
        "git show *",
        "git status",
        "cat *",
        "ls *",
        "npm test",
        "npx jest *",
        "npx playwright *",
        "node *",
        "head *",
        "tail *",
        "wc *",
    ],
    "deny": [
        "rm *",
        "mv *",
        "cp *",
        "git push *",
        "git commit *",
        "git add *",
        "git checkout *",
        "git reset *",
        "npm install *",
        "pip install *",
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

        # Copy MCP settings if provided — always overwrite so changes take effect on re-runs
        # CLI expects: <CLINE_DIR>/data/settings/cline_mcp_settings.json
        if self.mcp_settings_path and self.mcp_settings_path.exists():
            settings_dir = data_dir / "settings"
            settings_dir.mkdir(parents=True, exist_ok=True)
            dest = settings_dir / "cline_mcp_settings.json"
            import shutil as sh

            sh.copy2(self.mcp_settings_path, dest)
            logger.debug(f"Copied MCP settings to {dest}")

        # Write auth config so Cline doesn't prompt interactively.
        # Always overwrite so model changes and key rotations take effect.
        #
        # For OpenRouter, Cline uses provider-specific model ID keys:
        #   actModeOpenRouterModelId / planModeOpenRouterModelId
        # NOT the generic actModeApiModelId / planModeApiModelId (those are for
        # single-provider setups like Anthropic direct). Using the wrong keys
        # causes Cline to find no model config and fall back to its default (Claude Sonnet).
        global_state = data_dir / "globalState.json"
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        state = {
            "welcomeViewCompleted": True,
            "actModeApiProvider": "openrouter",
            "actModeOpenRouterModelId": self.model,
            "planModeApiProvider": "openrouter",
            "planModeOpenRouterModelId": self.plan_model,
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
            "--timeout",
            str(timeout),
        ]

        # Start in plan mode when a distinct plan model is configured.
        # In YOLO mode, Cline auto-switches plan→act after the plan is presented,
        # so both models are used: plan_model for planning, model for execution.
        # When plan_model == model (no separate planner), skip plan mode entirely.
        if self.plan_model != self.model:
            cmd.append("-p")

        if cwd:
            cmd.extend(["-c", str(cwd)])

        cmd.append(prompt)

        env = os.environ.copy()
        env["CLINE_DIR"] = str(self.cline_dir)
        env["CLINE_COMMAND_PERMISSIONS"] = json.dumps(self.command_permissions)

        logger.info(
            f"Running Cline (act={self.model}, plan={self.plan_model}, timeout={timeout}s)"
        )
        logger.debug(f"CLINE_DIR={self.cline_dir}")
        logger.debug(f"Prompt length: {len(prompt)} chars")

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        stuck_reason: Optional[str] = None
        lock = threading.Lock()

        def _reader(stream, lines: list[str], label: str) -> None:
            """Read lines from a stream in a background thread."""
            nonlocal stuck_reason
            for raw in stream:
                line = raw.rstrip("\n")
                lines.append(line)
                # Both stdout and stderr carry live Cline activity:
                # - stderr: task lifecycle events (Task started, tool calls, errors)
                # - stdout: tool results, file edits, command output
                # Log both at INFO so the full agent activity is visible in CI logs.
                if line.strip():
                    logger.info(f"[cline {label}] {line}")
                # Check for patterns that indicate Cline is stuck
                for pattern in _STUCK_PATTERNS:
                    if pattern.lower() in line.lower():
                        with lock:
                            stuck_reason = (
                                f"Detected stuck pattern: '{pattern}' in: {line}"
                            )
                        return  # stop reading, main loop will kill

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=str(cwd) if cwd else None,
            )

            # Stream stdout/stderr via background threads so neither blocks
            t_out = threading.Thread(
                target=_reader, args=(proc.stdout, stdout_lines, "stdout"), daemon=True
            )
            t_err = threading.Thread(
                target=_reader, args=(proc.stderr, stderr_lines, "stderr"), daemon=True
            )
            t_out.start()
            t_err.start()

            # Snapshot OpenRouter usage baseline for per-run spend tracking
            last_usage = _get_openrouter_usage()
            run_baseline = last_usage  # account total at process start

            # Wait for process, checking for stuck/timeout
            deadline = _time.monotonic() + timeout + 30
            check_count = 0
            while proc.poll() is None:
                now = _time.monotonic()

                # Hard timeout
                if now >= deadline:
                    proc.kill()
                    proc.wait()
                    raise subprocess.TimeoutExpired(cmd, timeout)

                # Check stuck patterns from reader threads
                with lock:
                    reason = stuck_reason
                if reason:
                    logger.warning(f"Killing Cline: {reason}")
                    proc.kill()
                    proc.wait()
                    raise ClineError(
                        f"Cline appears stuck: {reason}",
                        stdout="\n".join(stdout_lines),
                        stderr="\n".join(stderr_lines),
                        exit_code=-1,
                    )

                # Heartbeat every 30s: log at INFO so the run is visibly alive in CI.
                check_count += 1
                if check_count % 30 == 0:
                    current_usage = _get_openrouter_usage()
                    elapsed = int(now - (deadline - timeout - 30))
                    if current_usage is not None and last_usage is not None:
                        delta = current_usage - last_usage
                        run_total = (
                            current_usage - run_baseline
                            if run_baseline is not None
                            else None
                        )
                        run_str = (
                            f" / ${run_total:.4f} this run"
                            if run_total is not None
                            else ""
                        )
                        usage_str = f" | +${delta:.4f} this interval{run_str}"
                    elif current_usage is not None:
                        usage_str = f" | usage=${current_usage:.4f}"
                    else:
                        usage_str = ""
                    logger.info(
                        f"Cline running: {elapsed}s elapsed"
                        f" | {len(stdout_lines)} output lines"
                        f"{usage_str}"
                    )
                    if current_usage is not None:
                        last_usage = current_usage

                _time.sleep(1)

            # Process exited — let reader threads finish draining
            t_out.join(timeout=5)
            t_err.join(timeout=5)

            result_stdout = "\n".join(stdout_lines)
            result_stderr = "\n".join(stderr_lines)
            returncode = proc.returncode

            # Compute per-run cost from OpenRouter usage delta
            final_usage = get_openrouter_usage()
            run_cost: Optional[float] = None
            if final_usage is not None and run_baseline is not None:
                run_cost = max(0.0, final_usage - run_baseline)
                logger.info(f"Cline run cost: ${run_cost:.6f} USD")

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
            cost_usd=run_cost,
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

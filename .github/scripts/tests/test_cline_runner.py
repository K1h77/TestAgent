"""Tests for cline_runner module."""

import json
import subprocess
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.cline_runner import (
    ClineRunner,
    ClineResult,
    ClineError,
    DEFAULT_COMMAND_PERMISSIONS,
    READ_ONLY_PERMISSIONS,
)


class TestClineResult:
    """Tests for ClineResult dataclass."""

    def test_success_when_exit_zero(self):
        result = ClineResult(stdout="ok", stderr="", exit_code=0)
        assert result.success is True

    def test_not_success_when_nonzero(self):
        result = ClineResult(stdout="", stderr="error", exit_code=1)
        assert result.success is False

    def test_not_success_when_negative(self):
        result = ClineResult(stdout="", stderr="", exit_code=-1)
        assert result.success is False


class TestClineError:
    """Tests for ClineError exception."""

    def test_stores_details(self):
        err = ClineError("failed", stdout="out", stderr="err", exit_code=2)
        assert str(err) == "failed"
        assert err.stdout == "out"
        assert err.stderr == "err"
        assert err.exit_code == 2


class TestClineRunnerInit:
    """Tests for ClineRunner initialization."""

    @patch("shutil.which", return_value=None)
    def test_raises_when_cline_not_installed(self, mock_which, tmp_path):
        with pytest.raises(FileNotFoundError, match="Cline CLI is not installed"):
            ClineRunner(
                cline_dir=tmp_path / "cline",
                model="test/model",
            )

    @patch("shutil.which", return_value="/usr/bin/cline")
    def test_creates_cline_dir(self, mock_which, tmp_path):
        cline_dir = tmp_path / "cline-test"
        runner = ClineRunner(
            cline_dir=cline_dir,
            model="test/model",
        )
        assert cline_dir.exists()

    @patch("shutil.which", return_value="/usr/bin/cline")
    def test_copies_mcp_settings(self, mock_which, tmp_path):
        cline_dir = tmp_path / "cline-test"
        mcp_src = tmp_path / "mcp_settings.json"
        mcp_src.write_text('{"mcpServers": {}}')

        runner = ClineRunner(
            cline_dir=cline_dir,
            model="test/model",
            mcp_settings_path=mcp_src,
        )

        dest = cline_dir / "cline_mcp_settings.json"
        assert dest.exists()
        assert json.loads(dest.read_text()) == {"mcpServers": {}}

    @patch("shutil.which", return_value="/usr/bin/cline")
    def test_default_permissions(self, mock_which, tmp_path):
        runner = ClineRunner(cline_dir=tmp_path / "c", model="test/model")
        assert runner.command_permissions == DEFAULT_COMMAND_PERMISSIONS

    @patch("shutil.which", return_value="/usr/bin/cline")
    def test_custom_permissions(self, mock_which, tmp_path):
        perms = {"allow": ["ls"], "deny": [], "allowRedirects": False}
        runner = ClineRunner(
            cline_dir=tmp_path / "c",
            model="test/model",
            command_permissions=perms,
        )
        assert runner.command_permissions == perms


class TestClineRunnerRun:
    """Tests for ClineRunner.run()."""

    @patch("shutil.which", return_value="/usr/bin/cline")
    def test_empty_prompt_raises(self, mock_which, tmp_path):
        runner = ClineRunner(cline_dir=tmp_path / "c", model="test/model")
        with pytest.raises(ValueError, match="empty"):
            runner.run("")

    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.run")
    def test_successful_run(self, mock_subprocess, mock_which, tmp_path):
        mock_subprocess.return_value = MagicMock(
            stdout="task completed",
            stderr="",
            returncode=0,
        )

        runner = ClineRunner(cline_dir=tmp_path / "c", model="minimax/minimax-m2.5")
        result = runner.run("Fix the bug")

        assert result.success is True
        assert result.stdout == "task completed"
        assert result.exit_code == 0

        # Verify cline was called with correct args
        call_args = mock_subprocess.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "cline"
        assert "-y" in cmd
        assert "--model" in cmd
        assert "minimax/minimax-m2.5" in cmd

    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.run")
    def test_nonzero_exit_raises(self, mock_subprocess, mock_which, tmp_path):
        mock_subprocess.return_value = MagicMock(
            stdout="partial output",
            stderr="something went wrong",
            returncode=1,
        )

        runner = ClineRunner(cline_dir=tmp_path / "c", model="test/model")
        with pytest.raises(ClineError) as exc_info:
            runner.run("Fix the bug")

        assert exc_info.value.exit_code == 1
        assert exc_info.value.stderr == "something went wrong"

    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.run")
    def test_timeout_raises(self, mock_subprocess, mock_which, tmp_path):
        exc = subprocess.TimeoutExpired(cmd=["cline"], timeout=600)
        exc.stdout = "partial"
        exc.stderr = "timeout"
        mock_subprocess.side_effect = exc

        runner = ClineRunner(cline_dir=tmp_path / "c", model="test/model")
        with pytest.raises(ClineError, match="timed out"):
            runner.run("Fix the bug", timeout=600)

    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.run")
    def test_sets_env_vars(self, mock_subprocess, mock_which, tmp_path):
        mock_subprocess.return_value = MagicMock(
            stdout="ok", stderr="", returncode=0
        )

        cline_dir = tmp_path / "c"
        runner = ClineRunner(cline_dir=cline_dir, model="test/model")
        runner.run("test prompt")

        call_args = mock_subprocess.call_args
        env = call_args[1]["env"]
        assert env["CLINE_DIR"] == str(cline_dir)
        assert "CLINE_COMMAND_PERMISSIONS" in env


class TestPermissionConstants:
    """Tests for permission constants."""

    def test_default_allows_npm(self):
        assert "npm *" in DEFAULT_COMMAND_PERMISSIONS["allow"]

    def test_default_blocks_rm_rf(self):
        assert "rm -rf /" in DEFAULT_COMMAND_PERMISSIONS["deny"]

    def test_readonly_blocks_git_push(self):
        assert "git push *" in READ_ONLY_PERMISSIONS["deny"]

    def test_readonly_blocks_git_commit(self):
        assert "git commit *" in READ_ONLY_PERMISSIONS["deny"]

    def test_readonly_allows_npm_test(self):
        assert "npm test" in READ_ONLY_PERMISSIONS["allow"]

    def test_readonly_no_redirects(self):
        assert READ_ONLY_PERMISSIONS["allowRedirects"] is False

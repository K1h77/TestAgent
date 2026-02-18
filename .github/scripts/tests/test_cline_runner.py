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

        dest = cline_dir / "data" / "settings" / "cline_mcp_settings.json"
        assert dest.exists()
        assert json.loads(dest.read_text()) == {"mcpServers": {}}

    @patch("shutil.which", return_value="/usr/bin/cline")
    def test_overwrites_mcp_settings_on_reinit(self, mock_which, tmp_path):
        """MCP settings should always be overwritten, not skipped if already exist."""
        cline_dir = tmp_path / "cline-test"
        mcp_src = tmp_path / "mcp_settings.json"
        mcp_src.write_text('{"mcpServers": {"old": {}}}')

        # First init
        ClineRunner(cline_dir=cline_dir, model="test/model", mcp_settings_path=mcp_src)

        # Update source and reinit
        mcp_src.write_text('{"mcpServers": {"new": {}}}')
        ClineRunner(cline_dir=cline_dir, model="test/model", mcp_settings_path=mcp_src)

        dest = cline_dir / "data" / "settings" / "cline_mcp_settings.json"
        assert json.loads(dest.read_text()) == {"mcpServers": {"new": {}}}

    @patch("shutil.which", return_value="/usr/bin/cline")
    def test_overwrites_global_state_on_reinit(self, mock_which, tmp_path):
        """globalState.json should always reflect the current model, not be cached."""
        cline_dir = tmp_path / "cline-test"

        ClineRunner(cline_dir=cline_dir, model="model-v1")
        state_path = cline_dir / "data" / "globalState.json"
        assert json.loads(state_path.read_text())["actModeOpenRouterModelId"] == "model-v1"

        ClineRunner(cline_dir=cline_dir, model="model-v2")
        assert json.loads(state_path.read_text())["actModeOpenRouterModelId"] == "model-v2"

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

    @patch("time.sleep")
    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.Popen")
    def test_successful_run(self, mock_popen, mock_which, mock_sleep, tmp_path):
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, 0]
        mock_proc.returncode = 0
        mock_proc.stdout = iter(["task completed\n"])
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        runner = ClineRunner(cline_dir=tmp_path / "c", model="minimax/minimax-m2.5")
        result = runner.run("Fix the bug")

        assert result.success is True
        assert "task completed" in result.stdout
        assert result.exit_code == 0

        # Verify cline was called with correct args
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "cline"
        assert "-y" in cmd
        assert "--model" not in cmd  # model is set via globalState.json, not CLI flag
        assert "--timeout" in cmd
        assert "-p" not in cmd  # no separate plan_model, so act mode only

    @patch("time.sleep")
    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.Popen")
    def test_nonzero_exit_raises(self, mock_popen, mock_which, mock_sleep, tmp_path):
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, 1]
        mock_proc.returncode = 1
        mock_proc.stdout = iter(["partial output\n"])
        mock_proc.stderr = iter(["something went wrong\n"])
        mock_proc.wait.return_value = 1
        mock_popen.return_value = mock_proc

        runner = ClineRunner(cline_dir=tmp_path / "c", model="test/model")
        with pytest.raises(ClineError) as exc_info:
            runner.run("Fix the bug")

        assert exc_info.value.exit_code == 1
        assert "something went wrong" in exc_info.value.stderr

    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.Popen")
    def test_timeout_raises(self, mock_popen, mock_which, tmp_path):
        mock_popen.side_effect = FileNotFoundError("not found")

        runner = ClineRunner(cline_dir=tmp_path / "c", model="test/model")
        with pytest.raises(ClineError, match="not found"):
            runner.run("Fix the bug", timeout=600)

    @patch("time.sleep")
    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.Popen")
    def test_sets_env_vars(self, mock_popen, mock_which, mock_sleep, tmp_path):
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, 0]
        mock_proc.returncode = 0
        mock_proc.stdout = iter(["ok\n"])
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        cline_dir = tmp_path / "c"
        runner = ClineRunner(cline_dir=cline_dir, model="test/model")
        runner.run("test prompt")

        call_args = mock_popen.call_args
        env = call_args[1]["env"]
        assert env["CLINE_DIR"] == str(cline_dir)
        assert "CLINE_COMMAND_PERMISSIONS" in env


    @patch("time.sleep")
    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.Popen")
    def test_plan_flag_added_when_separate_plan_model(self, mock_popen, mock_which, mock_sleep, tmp_path):
        """When plan_model differs from model, -p flag must be passed so the planner is used."""
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, 0]
        mock_proc.returncode = 0
        mock_proc.stdout = iter(["done\n"])
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        runner = ClineRunner(
            cline_dir=tmp_path / "c",
            model="deepseek/deepseek-v3",
            plan_model="anthropic/claude-haiku-4.5",
        )
        runner.run("Build the feature")

        cmd = mock_popen.call_args[0][0]
        assert "-p" in cmd  # plan mode must be enabled so haiku is used for planning

    @patch("time.sleep")
    @patch("shutil.which", return_value="/usr/bin/cline")
    @patch("subprocess.Popen")
    def test_plan_flag_absent_when_no_separate_plan_model(self, mock_popen, mock_which, mock_sleep, tmp_path):
        """When plan_model is not set (defaults to model), -p flag must NOT be added."""
        mock_proc = MagicMock()
        mock_proc.poll.side_effect = [None, 0]
        mock_proc.returncode = 0
        mock_proc.stdout = iter(["done\n"])
        mock_proc.stderr = iter([])
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        runner = ClineRunner(cline_dir=tmp_path / "c", model="minimax/minimax-m2.5")
        runner.run("Review the code")

        cmd = mock_popen.call_args[0][0]
        assert "-p" not in cmd


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

"""Tests for git_ops module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.git_ops import (
    create_branch,
    commit_and_push,
    create_pr,
    get_pr_number,
    get_diff,
    get_changed_files,
    GitError,
)


class TestCreateBranch:
    """Tests for create_branch()."""

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="empty"):
            create_branch("")

    def test_none_name_raises(self):
        with pytest.raises(ValueError, match="empty"):
            create_branch(None)

    @patch("lib.git_ops._run_git")
    def test_calls_git_checkout_new_branch(self, mock_git):
        """When branch does not exist on remote, should create it with -b."""

        def side_effect(args, check=True):
            result = MagicMock()
            result.returncode = 0
            # ls-remote returns empty stdout → branch does not exist remotely
            if args[0] == "ls-remote":
                result.stdout = ""
            else:
                result.stdout = ""
            return result

        mock_git.side_effect = side_effect
        actual_branch = create_branch("ralph/issue-42")

        assert actual_branch == "ralph/issue-42"
        calls = [c.args[0] for c in mock_git.call_args_list]
        assert ["fetch", "origin"] in calls
        assert ["ls-remote", "--heads", "origin", "ralph/issue-42"] in calls
        assert ["checkout", "-b", "ralph/issue-42"] in calls

    @patch("lib.git_ops._run_git")
    def test_creates_versioned_branch_when_base_exists(self, mock_git):
        """When branch already exists on remote, should create -v2 version."""

        def side_effect(args, check=True):
            result = MagicMock()
            result.returncode = 0
            if args[0] == "ls-remote":
                # First call: base branch exists
                # Second call: -v2 does not exist
                if "ralph/issue-42-v2" in args:
                    result.stdout = ""
                else:
                    result.stdout = "abc123\trefs/heads/ralph/issue-42\n"
            else:
                result.stdout = ""
            return result

        mock_git.side_effect = side_effect
        actual_branch = create_branch("ralph/issue-42")

        assert actual_branch == "ralph/issue-42-v2"
        calls = [c.args[0] for c in mock_git.call_args_list]
        assert ["checkout", "-b", "ralph/issue-42-v2"] in calls
        # Should NOT try to checkout/reset the existing branch
        assert ["checkout", "ralph/issue-42"] not in calls
        assert ["reset", "--hard", "origin/ralph/issue-42"] not in calls

    @patch("lib.git_ops._run_git")
    def test_git_failure_raises(self, mock_git):
        mock_git.side_effect = GitError("branch exists", exit_code=128)
        with pytest.raises(GitError):
            create_branch("ralph/issue-42")


class TestCommitAndPush:
    """Tests for commit_and_push()."""

    def test_empty_message_raises(self):
        with pytest.raises(ValueError, match="message"):
            commit_and_push("", "branch")

    def test_empty_branch_raises(self):
        with pytest.raises(ValueError, match="Branch name"):
            commit_and_push("message", "")

    @patch("lib.git_ops._run_git")
    def test_no_changes_raises(self, mock_git):
        """If git status --porcelain returns empty, should raise GitError."""

        def side_effect(args, check=True):
            result = MagicMock()
            if args[0] == "status":
                result.stdout = ""
                result.returncode = 0
            else:
                result.stdout = ""
                result.returncode = 0
            return result

        mock_git.side_effect = side_effect

        with pytest.raises(GitError, match="No changes"):
            commit_and_push("fix stuff", "ralph/issue-1")

    @patch("lib.git_ops._run_git")
    def test_successful_commit_and_push(self, mock_git):
        """Should call git add, check status, commit, and push (check=False)."""

        def side_effect(args, check=True):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "M server.js\n" if args[0] == "status" else ""
            result.stderr = ""
            return result

        mock_git.side_effect = side_effect
        commit_and_push("fix bug", "ralph/issue-1")

        calls = [c.args[0] for c in mock_git.call_args_list]
        assert ["add", "-A"] in calls
        assert ["status", "--porcelain"] in calls
        assert ["commit", "-m", "fix bug"] in calls
        assert ["push", "origin", "ralph/issue-1"] in calls

    @patch("lib.git_ops._run_git")
    def test_push_retries_after_non_fast_forward(self, mock_git):
        """On non-fast-forward push rejection, should pull --rebase then retry push."""
        push_attempt = 0

        def side_effect(args, check=True):
            nonlocal push_attempt
            result = MagicMock()
            result.stdout = "M server.js\n" if args[0] == "status" else ""
            result.stderr = ""
            if args[0] == "push":
                push_attempt += 1
                if push_attempt == 1:
                    # First push attempt: rejected
                    result.returncode = 1
                    result.stderr = "! [rejected] non-fast-forward"
                else:
                    result.returncode = 0
            else:
                result.returncode = 0
            return result

        mock_git.side_effect = side_effect
        commit_and_push("fix bug", "ralph/issue-1")

        calls = [c.args[0] for c in mock_git.call_args_list]
        # Should have attempted a pull --rebase after rejection
        assert ["pull", "--rebase", "origin", "ralph/issue-1"] in calls
        # And pushed a second time
        assert push_attempt == 2

    @patch("lib.git_ops._run_git")
    def test_non_fast_forward_raises_after_rebase_fails(self, mock_git):
        """If the retry push also fails, should raise GitError."""

        def side_effect(args, check=True):
            result = MagicMock()
            result.stdout = "M server.js\n" if args[0] == "status" else ""
            if args[0] == "push":
                result.returncode = 1
                result.stderr = "! [rejected] non-fast-forward"
            elif check is False:
                result.returncode = 0
                result.stderr = ""
            else:
                result.returncode = 0
                result.stderr = ""
            return result

        # Make the second push (after rebase) also fail — _run_git with check=True raises
        call_count = {"push": 0}

        def side_effect2(args, check=True):
            result = MagicMock()
            result.stdout = "M server.js\n" if args[0] == "status" else ""
            result.stderr = ""
            result.returncode = 0
            if args[0] == "push":
                call_count["push"] += 1
                if call_count["push"] == 1:
                    result.returncode = 1
                    result.stderr = "! [rejected] non-fast-forward"
                else:
                    # Second push (check=True default) raises via _run_git
                    raise GitError("push failed again", exit_code=1)
            return result

        mock_git.side_effect = side_effect2
        with pytest.raises(GitError):
            commit_and_push("fix bug", "ralph/issue-1")


class TestCreatePr:
    """Tests for create_pr()."""

    def test_empty_title_raises(self):
        with pytest.raises(ValueError, match="title"):
            create_pr("", "body", "main", "feature")

    def test_empty_head_raises(self):
        with pytest.raises(ValueError, match="head"):
            create_pr("title", "body", "main", "")

    @patch("lib.git_ops._run_gh")
    def test_returns_pr_url(self, mock_gh):
        mock_gh.return_value = MagicMock(
            stdout="https://github.com/user/repo/pull/42\n",
            returncode=0,
        )
        url = create_pr("Fix bug", "Description", "main", "ralph/issue-42")
        assert url == "https://github.com/user/repo/pull/42"

    @patch("lib.git_ops._run_gh")
    def test_empty_url_raises(self, mock_gh):
        mock_gh.return_value = MagicMock(stdout="", returncode=0)
        with pytest.raises(GitError, match="no URL"):
            create_pr("Fix bug", "Description", "main", "ralph/issue-42")


class TestGetPrNumber:
    """Tests for get_pr_number()."""

    def test_extracts_from_url(self):
        assert get_pr_number("https://github.com/user/repo/pull/42") == "42"

    def test_handles_trailing_slash(self):
        assert get_pr_number("https://github.com/user/repo/pull/42/") == "42"


class TestGetDiff:
    """Tests for get_diff()."""

    @patch("lib.git_ops._run_git")
    def test_returns_diff_string(self, mock_git):
        mock_git.return_value = MagicMock(stdout="diff --git a/file.js b/file.js\n")
        result = get_diff("main")
        assert "diff --git" in result


class TestGetChangedFiles:
    """Tests for get_changed_files()."""

    @patch("lib.git_ops._run_git")
    def test_returns_file_list(self, mock_git):
        mock_git.return_value = MagicMock(stdout="server.js\napp.js\n")
        files = get_changed_files("main")
        assert files == ["server.js", "app.js"]

    @patch("lib.git_ops._run_git")
    def test_empty_diff_returns_empty_list(self, mock_git):
        mock_git.return_value = MagicMock(stdout="")
        files = get_changed_files("main")
        assert files == []

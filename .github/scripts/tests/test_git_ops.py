"""Tests for git_ops module."""

import subprocess
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
    def test_calls_git_checkout(self, mock_git):
        mock_git.return_value = MagicMock(returncode=0)
        create_branch("ralph/issue-42")
        mock_git.assert_called_once_with(["checkout", "-b", "ralph/issue-42"])

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
        """Should call git add, check status, commit, and push."""
        call_count = 0

        def side_effect(args, check=True):
            nonlocal call_count
            call_count += 1
            result = MagicMock()
            if args[0] == "status":
                result.stdout = "M server.js\n"
            else:
                result.stdout = ""
            result.returncode = 0
            return result

        mock_git.side_effect = side_effect
        commit_and_push("fix bug", "ralph/issue-1")
        assert call_count == 4  # add, status, commit, push


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

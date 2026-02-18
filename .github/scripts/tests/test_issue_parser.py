"""Tests for issue_parser module."""

import os
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.issue_parser import parse_issue, require_env, Issue


class TestParseIssue:
    """Tests for parse_issue()."""

    def test_valid_input(self):
        result = parse_issue("42", "Fix the login bug", "The login form crashes on submit")
        assert result == Issue(number=42, title="Fix the login bug", body="The login form crashes on submit")

    def test_strips_whitespace(self):
        result = parse_issue("  42  ", "  Fix bug  ", "  Description  ")
        assert result.number == 42
        assert result.title == "Fix bug"
        assert result.body == "Description"

    def test_missing_number_raises(self):
        with pytest.raises(ValueError, match="missing or empty"):
            parse_issue("", "Title", "Body")

    def test_none_number_raises(self):
        with pytest.raises(ValueError, match="missing or empty"):
            parse_issue(None, "Title", "Body")

    def test_non_numeric_number_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            parse_issue("abc", "Title", "Body")

    def test_negative_number_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            parse_issue("-1", "Title", "Body")

    def test_zero_number_raises(self):
        with pytest.raises(ValueError, match="positive integer"):
            parse_issue("0", "Title", "Body")

    def test_missing_title_raises(self):
        with pytest.raises(ValueError, match="title"):
            parse_issue("1", "", "Body")

    def test_none_title_raises(self):
        with pytest.raises(ValueError, match="title"):
            parse_issue("1", None, "Body")

    def test_whitespace_only_title_raises(self):
        with pytest.raises(ValueError, match="title"):
            parse_issue("1", "   ", "Body")

    def test_missing_body_raises(self):
        with pytest.raises(ValueError, match="body"):
            parse_issue("1", "Title", "")

    def test_none_body_raises(self):
        with pytest.raises(ValueError, match="body"):
            parse_issue("1", "Title", None)

    def test_whitespace_only_body_raises(self):
        with pytest.raises(ValueError, match="body"):
            parse_issue("1", "Title", "   ")

    def test_issue_is_frozen(self):
        issue = parse_issue("1", "Title", "Body")
        with pytest.raises(AttributeError):
            issue.number = 2


class TestRequireEnv:
    """Tests for require_env()."""

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR_123", "hello")
        assert require_env("TEST_VAR_123") == "hello"

    def test_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR_123", "  hello  ")
        assert require_env("TEST_VAR_123") == "hello"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("TEST_MISSING_VAR_XYZ", raising=False)
        with pytest.raises(ValueError, match="TEST_MISSING_VAR_XYZ"):
            require_env("TEST_MISSING_VAR_XYZ")

    def test_raises_when_empty(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR_123", "")
        with pytest.raises(ValueError, match="TEST_VAR_123"):
            require_env("TEST_VAR_123")

    def test_raises_when_whitespace_only(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR_123", "   ")
        with pytest.raises(ValueError, match="TEST_VAR_123"):
            require_env("TEST_VAR_123")

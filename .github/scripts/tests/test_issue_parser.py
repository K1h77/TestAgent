"""Tests for issue_parser module."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.issue_parser import parse_issue, require_env, Issue


class TestParseIssue:
    """Tests for parse_issue()."""

    def test_valid_input(self):
        result = parse_issue(
            "42", "Fix the login bug", "The login form crashes on submit"
        )
        assert result == Issue(
            number=42,
            title="Fix the login bug",
            body="The login form crashes on submit",
        )

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


class TestIssueLabels:
    """Tests for labels field and is_frontend() on Issue."""

    def test_labels_default_empty(self):
        issue = parse_issue("1", "Title", "Body")
        assert issue.labels == frozenset()

    def test_labels_single(self):
        issue = parse_issue("1", "Title", "Body", labels="frontend")
        assert issue.labels == frozenset({"frontend"})

    def test_labels_multiple(self):
        issue = parse_issue("1", "Title", "Body", labels="frontend,bug,help wanted")
        assert issue.labels == frozenset({"frontend", "bug", "help wanted"})

    def test_labels_stripped_and_lowercased(self):
        issue = parse_issue("1", "Title", "Body", labels="  Frontend  ,  BUG  ")
        assert "frontend" in issue.labels
        assert "bug" in issue.labels

    def test_labels_empty_string(self):
        issue = parse_issue("1", "Title", "Body", labels="")
        assert issue.labels == frozenset()

    def test_labels_whitespace_only_string(self):
        issue = parse_issue("1", "Title", "Body", labels="   ,  ,  ")
        assert issue.labels == frozenset()

    def test_is_frontend_true(self):
        issue = parse_issue("1", "Title", "Body", labels="frontend")
        assert issue.is_frontend() is True

    def test_is_frontend_true_case_insensitive_input(self):
        issue = parse_issue("1", "Title", "Body", labels="Frontend")
        assert issue.is_frontend() is True

    def test_is_frontend_false_no_labels(self):
        issue = parse_issue("1", "Title", "Body")
        assert issue.is_frontend() is False

    def test_is_frontend_false_other_labels(self):
        issue = parse_issue("1", "Title", "Body", labels="bug,backend,performance")
        assert issue.is_frontend() is False

    def test_is_frontend_true_among_many_labels(self):
        issue = parse_issue("1", "Title", "Body", labels="bug,frontend,help wanted")
        assert issue.is_frontend() is True

    def test_valid_input_includes_labels(self):
        issue = parse_issue(
            "42", "Fix UI bug", "Button is broken", labels="frontend,bug"
        )
        assert issue.number == 42
        assert issue.title == "Fix UI bug"
        assert issue.body == "Button is broken"
        assert "frontend" in issue.labels
        assert "bug" in issue.labels

    def test_labels_field_is_frozenset(self):
        issue = parse_issue("1", "Title", "Body", labels="frontend")
        assert isinstance(issue.labels, frozenset)

    def test_labels_immutable_via_frozen_dataclass(self):
        issue = parse_issue("1", "Title", "Body", labels="frontend")
        with pytest.raises(AttributeError):
            issue.labels = frozenset({"other"})


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

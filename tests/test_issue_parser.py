"""Tests for issue_parser module."""

import pytest
from pydantic import ValidationError

from clanker.lib.issue_parser import parse_issue, Issue
from clanker.lib.env_settings import IssueSettings, ApiSettings, ReviewSettings


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


class TestIssueSettings:
    """Tests for IssueSettings pydantic model."""

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("ISSUE_NUMBER", "42")
        monkeypatch.setenv("ISSUE_TITLE", "Fix bug")
        monkeypatch.setenv("ISSUE_BODY", "Description")
        settings = IssueSettings()
        assert settings.issue_number == "42"
        assert settings.issue_title == "Fix bug"
        assert settings.issue_body == "Description"
        assert settings.issue_labels == ""

    def test_loads_labels(self, monkeypatch):
        monkeypatch.setenv("ISSUE_NUMBER", "1")
        monkeypatch.setenv("ISSUE_TITLE", "T")
        monkeypatch.setenv("ISSUE_BODY", "B")
        monkeypatch.setenv("ISSUE_LABELS", "frontend,bug")
        settings = IssueSettings()
        assert settings.issue_labels == "frontend,bug"

    def test_raises_when_required_missing(self, monkeypatch):
        monkeypatch.delenv("ISSUE_NUMBER", raising=False)
        monkeypatch.delenv("ISSUE_TITLE", raising=False)
        monkeypatch.delenv("ISSUE_BODY", raising=False)
        with pytest.raises(ValidationError):
            IssueSettings()


class TestApiSettings:
    """Tests for ApiSettings pydantic model."""

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-123")
        settings = ApiSettings()
        assert settings.openrouter_api_key == "sk-test-123"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(ValidationError):
            ApiSettings()


class TestReviewSettings:
    """Tests for ReviewSettings pydantic model."""

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("PR_NUMBER", "99")
        monkeypatch.setenv("BRANCH", "ralph/issue-42-fix")
        settings = ReviewSettings()
        assert settings.pr_number == "99"
        assert settings.branch == "ralph/issue-42-fix"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("PR_NUMBER", raising=False)
        monkeypatch.delenv("BRANCH", raising=False)
        with pytest.raises(ValidationError):
            ReviewSettings()

"""Tests for self_review — parse_verdict and frontend-gating behaviour.

parse_verdict is extracted here to avoid importing the top-level self_review
module (which pulls in ralph.lib.agent_config → pyyaml at import time and
would fail in environments without the full dependency set installed).
"""

import re
from unittest.mock import MagicMock


# ── Inline copy of parse_verdict so we can test it without importing the full
#    self_review module (which has heavy top-level imports).  The logic must
#    stay in sync with the real implementation in self_review.py.
def parse_verdict(review_output: str) -> str:
    """Mirror of self_review.parse_verdict — kept in sync manually."""
    clean_output = re.sub(r"[*_`>#\-]", " ", review_output)

    for line in clean_output.splitlines():
        line_stripped = line.strip().lower()
        if "verdict" in line_stripped and ":" in line_stripped:
            after_colon = line_stripped.split(":", 1)[1].strip()
            if (
                "needs changes" in after_colon
                or "needs_changes" in after_colon
                or "needs changes" in line_stripped
            ):
                return "NEEDS CHANGES"
            if "lgtm" in after_colon:
                return "LGTM"

    clean_lower = clean_output.lower()
    if "needs changes" in clean_lower or "needs_changes" in clean_lower:
        idx = clean_lower.find("needs changes")
        if idx != -1 and "verdict" in clean_lower[max(0, idx - 100) : idx + 50]:
            return "NEEDS CHANGES"

    return "LGTM"


# ── parse_verdict ────────────────────────────────────────────────────────────


class TestParseVerdict:
    """Tests for parse_verdict()."""

    def test_lgtm_simple(self):
        assert parse_verdict("Verdict: LGTM") == "LGTM"

    def test_needs_changes_simple(self):
        assert parse_verdict("Verdict: NEEDS CHANGES") == "NEEDS CHANGES"

    def test_lgtm_bold_markdown(self):
        assert parse_verdict("**Verdict: LGTM**") == "LGTM"

    def test_needs_changes_bold_markdown(self):
        assert parse_verdict("**Verdict: NEEDS CHANGES**") == "NEEDS CHANGES"

    def test_lgtm_in_blockquote(self):
        assert parse_verdict("> Verdict: LGTM") == "LGTM"

    def test_needs_changes_in_blockquote(self):
        assert parse_verdict("> Verdict: NEEDS CHANGES") == "NEEDS CHANGES"

    def test_needs_underscore_variant(self):
        assert parse_verdict("Verdict: NEEDS_CHANGES") == "NEEDS CHANGES"

    def test_case_insensitive_lgtm(self):
        assert parse_verdict("verdict: lgtm") == "LGTM"

    def test_case_insensitive_needs_changes(self):
        assert parse_verdict("verdict: needs changes") == "NEEDS CHANGES"

    def test_no_verdict_defaults_to_lgtm(self):
        # Lenient: no clear verdict → LGTM
        assert parse_verdict("The code looks reasonable overall.") == "LGTM"

    def test_empty_string_defaults_to_lgtm(self):
        assert parse_verdict("") == "LGTM"

    def test_needs_changes_beats_lgtm_when_only_needs_changes(self):
        output = (
            "Overall looks okay.\n\nVerdict: NEEDS CHANGES\n\nPlease fix the tests."
        )
        assert parse_verdict(output) == "NEEDS CHANGES"

    def test_multiline_with_lgtm_verdict(self):
        output = (
            "## Review\n\n"
            "The implementation is correct.\n"
            "Tests pass.\n\n"
            "Verdict: LGTM\n"
        )
        assert parse_verdict(output) == "LGTM"

    def test_verdict_with_surrounding_noise(self):
        output = "---\n**Verdict: NEEDS CHANGES**\n---"
        assert parse_verdict(output) == "NEEDS CHANGES"


# ── Frontend-gating: visual verdict only read for frontend issues ─────────────


class TestVisualVerdictGating:
    """
    Tests that the is_frontend() gate correctly controls whether
    read_visual_verdict would be called.  We test this by simulating
    the exact conditional pattern used in self_review.py:

        visual_verdict = read_visual_verdict(path) if issue.is_frontend() else None
    """

    def _call_with_gate(self, issue, mock_rvv, path):
        """Reproduce the gating expression from self_review.py."""
        return mock_rvv(path) if issue.is_frontend() else None

    def _frontend_issue(self):
        from ralph.lib.issue_parser import parse_issue

        return parse_issue(
            "1", "Fix button colour", "Button is wrong", labels="frontend"
        )

    def _backend_issue(self):
        from ralph.lib.issue_parser import parse_issue

        return parse_issue("2", "Fix API timeout", "Times out", labels="backend,bug")

    def _unlabelled_issue(self):
        from ralph.lib.issue_parser import parse_issue

        return parse_issue("3", "Some task", "Some description")

    def test_frontend_issue_reads_visual_verdict(self, tmp_path):
        mock_rvv = MagicMock(return_value="FEATURE_FOUND")
        result = self._call_with_gate(self._frontend_issue(), mock_rvv, tmp_path)
        mock_rvv.assert_called_once_with(tmp_path)
        assert result == "FEATURE_FOUND"

    def test_non_frontend_issue_skips_visual_verdict(self, tmp_path):
        mock_rvv = MagicMock(return_value="FEATURE_FOUND")
        result = self._call_with_gate(self._backend_issue(), mock_rvv, tmp_path)
        mock_rvv.assert_not_called()
        assert result is None

    def test_unlabelled_issue_skips_visual_verdict(self, tmp_path):
        mock_rvv = MagicMock(return_value="SOMETHING")
        result = self._call_with_gate(self._unlabelled_issue(), mock_rvv, tmp_path)
        mock_rvv.assert_not_called()
        assert result is None

    def test_frontend_among_many_labels_still_triggers(self, tmp_path):
        from ralph.lib.issue_parser import parse_issue

        issue = parse_issue("4", "Title", "Body", labels="bug,frontend,ui")
        mock_rvv = MagicMock(return_value="OK")
        result = self._call_with_gate(issue, mock_rvv, tmp_path)
        mock_rvv.assert_called_once()
        assert result == "OK"

    def test_visual_section_omitted_when_verdict_none(self):
        """When visual_verdict is None the visual_section string should be empty."""
        visual_verdict = None
        visual_section = (
            f"\n\n### Visual QA\n{visual_verdict}" if visual_verdict else ""
        )
        assert visual_section == ""

    def test_visual_section_present_when_verdict_set(self):
        """When visual_verdict is a string the visual_section should contain it."""
        visual_verdict = "FEATURE_FOUND"
        visual_section = (
            f"\n\n### Visual QA\n{visual_verdict}" if visual_verdict else ""
        )
        assert "FEATURE_FOUND" in visual_section
        assert "Visual QA" in visual_section

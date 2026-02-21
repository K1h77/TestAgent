from clanker.lib.logging_config import format_summary, format_review_summary


class TestFormatSummary:
    def test_started_status(self):
        result = format_summary({"status": "started", "issue_number": 7})
        assert "Ralph Agent" in result
        assert "#7" in result
        assert "working on" in result.lower()

    def test_pr_created_with_tests_passing(self):
        result = format_summary(
            {
                "status": "pr_created",
                "issue_number": 7,
                "pr_url": "https://github.com/org/repo/pull/99",
                "tests_passed": True,
                "coding_attempts": 2,
            }
        )
        assert "https://github.com/org/repo/pull/99" in result
        assert "passing" in result
        assert "2" in result

    def test_pr_created_with_tests_failing(self):
        result = format_summary(
            {
                "status": "pr_created",
                "issue_number": 7,
                "pr_url": "https://github.com/org/repo/pull/99",
                "tests_passed": False,
                "coding_attempts": 3,
            }
        )
        assert "partially passing" in result

    def test_failed_status_includes_error(self):
        result = format_summary(
            {
                "status": "failed",
                "issue_number": 7,
                "error": "Push rejected",
            }
        )
        assert "failed" in result.lower()
        assert "Push rejected" in result
        assert "#7" in result

    def test_unknown_status_shows_status_string(self):
        result = format_summary({"status": "pending"})
        assert "pending" in result

    def test_missing_optional_fields_do_not_raise(self):
        result = format_summary({"status": "pr_created"})
        assert isinstance(result, str)


class TestFormatReviewSummary:
    def test_verdict_appears_in_header(self):
        result = format_review_summary("Looks good.", "PASSED")
        assert "PASSED" in result

    def test_review_output_included(self):
        result = format_review_summary("Change foo to bar.", "NEEDS ATTENTION")
        assert "Change foo to bar." in result

    def test_long_output_truncated(self):
        long_output = "x" * 4000
        result = format_review_summary(long_output, "PASSED")
        assert "truncated" in result
        assert len(result) < len(long_output) + 200

    def test_short_output_not_truncated(self):
        short = "Short review."
        result = format_review_summary(short, "PASSED")
        assert "Short review." in result
        assert "truncated" not in result

    def test_contains_automated_footer(self):
        result = format_review_summary("ok", "PASSED")
        assert "Ralph Agent" in result

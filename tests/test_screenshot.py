import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from clanker.lib.screenshot import (
    take_screenshot,
    embed_screenshots_markdown,
    _to_relative_path,
    _recover_misnamed_screenshot,
    _validate_screenshot,
    _parse_selected_paths,
    _fallback_screenshot_selection,
)
from clanker.lib.cline_runner import ClineError


class TestTakeScreenshot:
    """Tests for take_screenshot()."""

    def test_creates_parent_directory(self, tmp_path):
        """Should create the parent directory for the screenshot."""
        mock_cline = MagicMock()
        output_path = tmp_path / "subdir" / "screenshot.png"

        # Cline succeeds but doesn't actually create the file
        take_screenshot(mock_cline, output_path)

        assert output_path.parent.exists()

    def test_returns_path_when_file_exists(self, tmp_path):
        """Should return the path when screenshot is created successfully."""
        output_path = tmp_path / "screenshot.png"

        mock_cline = MagicMock()

        # Simulate Cline creating the file
        def create_file(*args, **kwargs):
            output_path.write_bytes(b"\x89PNG fake image data")
            return MagicMock(success=True)

        mock_cline.run.side_effect = create_file

        result = take_screenshot(mock_cline, output_path)
        assert result == output_path

    def test_returns_none_when_cline_fails(self, tmp_path):
        """Should return None (not raise) when Cline fails."""
        mock_cline = MagicMock()
        mock_cline.run.side_effect = ClineError("failed")

        output_path = tmp_path / "screenshot.png"
        result = take_screenshot(mock_cline, output_path)
        assert result is None

    def test_returns_none_when_file_not_created(self, tmp_path):
        """Should return None when Cline succeeds but file doesn't exist."""
        mock_cline = MagicMock()
        output_path = tmp_path / "screenshot.png"

        result = take_screenshot(mock_cline, output_path)
        assert result is None

    def test_adopts_misnamed_png_when_expected_file_missing(self, tmp_path):
        """When expected file is missing but another PNG exists, should rename and return it."""
        output_path = tmp_path / "before.png"

        def save_differently(*args, **kwargs):
            # Cline saved to a different filename
            (tmp_path / "switch.png").write_bytes(b"\x89PNG fake")
            return MagicMock(success=True)

        mock_cline = MagicMock()
        mock_cline.run.side_effect = save_differently

        with patch("clanker.lib.screenshot.logger") as mock_logger:
            result = take_screenshot(mock_cline, output_path)
            # Should rename switch.png → before.png and return the path
            assert result == output_path
            assert output_path.exists()
            # Should log a warning mentioning the rename
            warning_calls = " ".join(str(c) for c in mock_logger.warning.call_args_list)
            assert "switch.png" in warning_calls

    def test_returns_none_when_file_empty(self, tmp_path):
        """Should return None when screenshot file is 0 bytes."""
        output_path = tmp_path / "screenshot.png"

        mock_cline = MagicMock()

        def create_empty(*args, **kwargs):
            output_path.write_bytes(b"")
            return MagicMock(success=True)

        mock_cline.run.side_effect = create_empty

        result = take_screenshot(mock_cline, output_path)
        assert result is None

    def test_prompt_includes_before_context(self, tmp_path):
        """Should include 'BEFORE' context in the prompt sent to Cline."""
        mock_cline = MagicMock()
        output_path = tmp_path / "screenshot.png"

        take_screenshot(mock_cline, output_path)

        call_args = mock_cline.run.call_args
        prompt = call_args[0][0]
        assert "BEFORE" in prompt


class TestEmbedScreenshotsMarkdown:
    """Tests for embed_screenshots_markdown()."""

    def test_both_screenshots(self, tmp_path):
        before = tmp_path / "screenshots" / "before.png"
        after1 = tmp_path / "screenshots" / "after_01.png"
        after2 = tmp_path / "screenshots" / "after_02.png"

        md = embed_screenshots_markdown(
            before, [after1, after2], "clanker/issue-1", "user/repo"
        )

        assert "Before" in md
        assert "After" in md
        assert "raw.githubusercontent.com" in md
        assert "clanker/issue-1" in md
        assert "after_01.png" in md
        assert "after_02.png" in md

    def test_multiple_after_labels(self, tmp_path):
        after1 = tmp_path / "screenshots" / "after_01.png"
        after2 = tmp_path / "screenshots" / "after_02.png"

        md = embed_screenshots_markdown(None, [after1, after2], "branch", "user/repo")

        assert "After 1" in md
        assert "After 2" in md

    def test_single_after_no_number_label(self, tmp_path):
        after = tmp_path / "screenshots" / "after_01.png"

        md = embed_screenshots_markdown(None, [after], "branch", "user/repo")

        assert "![After]" in md
        assert "After 1" not in md

    def test_no_screenshots(self):
        md = embed_screenshots_markdown(None, [], "branch", "user/repo")
        assert "No screenshots" in md

    def test_only_before(self, tmp_path):
        before = tmp_path / "screenshots" / "before.png"
        md = embed_screenshots_markdown(before, [], "branch", "user/repo")
        assert "Before" in md
        assert "After" not in md

    def test_only_after(self, tmp_path):
        after = tmp_path / "screenshots" / "after_01.png"
        md = embed_screenshots_markdown(None, [after], "branch", "user/repo")
        assert "After" in md
        assert "Before" not in md


class TestToRelativePath:
    def test_extracts_from_screenshots_dir(self):
        path = Path("/home/user/project/screenshots/before.png")
        assert _to_relative_path(path) == "screenshots/before.png"

    def test_falls_back_to_filename(self):
        path = Path("/home/user/project/images/before.png")
        assert _to_relative_path(path) == "before.png"

    def test_nested_screenshots_dir(self):
        path = Path("/home/user/project/screenshots/subdir/after.png")
        assert _to_relative_path(path) == "screenshots/subdir/after.png"


class TestRecoverMisnamedScreenshot:
    def test_returns_none_when_no_pngs(self, tmp_path):
        output_path = tmp_path / "before.png"
        result = _recover_misnamed_screenshot(output_path)
        assert result is None

    def test_renames_most_recent_png_to_output_path(self, tmp_path):
        output_path = tmp_path / "before.png"
        other = tmp_path / "screenshot_random.png"
        other.write_bytes(b"\x89PNG data")
        result = _recover_misnamed_screenshot(output_path)
        assert result == output_path
        assert output_path.exists()
        assert not other.exists()

    def test_picks_most_recently_modified(self, tmp_path):
        output_path = tmp_path / "before.png"
        old = tmp_path / "old.png"
        new = tmp_path / "new.png"
        old.write_bytes(b"\x89PNG old")
        import time

        time.sleep(0.01)
        new.write_bytes(b"\x89PNG new")
        _recover_misnamed_screenshot(output_path)
        assert output_path.read_bytes() == b"\x89PNG new"


class TestValidateScreenshot:
    def test_returns_path_for_valid_file(self, tmp_path):
        p = tmp_path / "shot.png"
        p.write_bytes(b"\x89PNG data")
        assert _validate_screenshot(p) == p

    def test_returns_none_for_empty_file(self, tmp_path):
        p = tmp_path / "shot.png"
        p.write_bytes(b"")
        assert _validate_screenshot(p) is None

    def test_returns_none_when_missing_and_no_recovery(self, tmp_path):
        p = tmp_path / "shot.png"
        assert _validate_screenshot(p) is None

    def test_recovers_misnamed_file(self, tmp_path):
        output_path = tmp_path / "before.png"
        other = tmp_path / "other.png"
        other.write_bytes(b"\x89PNG data")
        result = _validate_screenshot(output_path)
        assert result == output_path
        assert output_path.exists()


class TestParseSelectedPaths:
    def test_returns_empty_when_verdict_missing(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        assert _parse_selected_paths(verdict_path, tmp_path) == []

    def test_returns_empty_when_verdict_empty(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        verdict_path.write_text("")
        assert _parse_selected_paths(verdict_path, tmp_path) == []

    def test_returns_empty_when_no_selected_line(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        verdict_path.write_text("VISUAL: OK\nNo selection here")
        assert _parse_selected_paths(verdict_path, tmp_path) == []

    def test_parses_single_file(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        img = tmp_path / "after_01.png"
        img.write_bytes(b"\x89PNG")
        verdict_path.write_text("VISUAL: OK\nSELECTED: after_01.png")
        result = _parse_selected_paths(verdict_path, tmp_path)
        assert result == [img]

    def test_parses_multiple_comma_separated_files(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        img1 = tmp_path / "after_01.png"
        img2 = tmp_path / "after_02.png"
        img1.write_bytes(b"\x89PNG")
        img2.write_bytes(b"\x89PNG")
        verdict_path.write_text("SELECTED: after_01.png, after_02.png")
        result = _parse_selected_paths(verdict_path, tmp_path)
        assert result == [img1, img2]

    def test_skips_files_that_dont_exist(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        img = tmp_path / "after_01.png"
        img.write_bytes(b"\x89PNG")
        verdict_path.write_text("SELECTED: after_01.png, ghost.png")
        result = _parse_selected_paths(verdict_path, tmp_path)
        assert result == [img]

    def test_skips_empty_files(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        img = tmp_path / "after_01.png"
        img.write_bytes(b"")
        verdict_path.write_text("SELECTED: after_01.png")
        result = _parse_selected_paths(verdict_path, tmp_path)
        assert result == []

    def test_case_insensitive_selected_keyword(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        img = tmp_path / "after_01.png"
        img.write_bytes(b"\x89PNG")
        verdict_path.write_text("selected: after_01.png")
        result = _parse_selected_paths(verdict_path, tmp_path)
        assert result == [img]

    def test_inline_selected_on_same_line_as_visual(self, tmp_path):
        verdict_path = tmp_path / "visual_verdict.txt"
        img = tmp_path / "after_01.png"
        img.write_bytes(b"\x89PNG")
        verdict_path.write_text("VISUAL: OK SELECTED: after_01.png")
        result = _parse_selected_paths(verdict_path, tmp_path)
        assert result == [img]


class TestFallbackScreenshotSelection:
    def test_returns_after_pngs_sorted_by_name(self, tmp_path):
        b = tmp_path / "after_02.png"
        a = tmp_path / "after_01.png"
        a.write_bytes(b"\x89PNG")
        b.write_bytes(b"\x89PNG")
        result = _fallback_screenshot_selection(tmp_path)
        assert result == [a, b]

    def test_excludes_before_png(self, tmp_path):
        before = tmp_path / "before.png"
        before.write_bytes(b"\x89PNG")
        result = _fallback_screenshot_selection(tmp_path)
        assert result == []

    def test_falls_back_to_any_png_when_no_after_prefix(self, tmp_path):
        img = tmp_path / "screenshot_123.png"
        img.write_bytes(b"\x89PNG")
        result = _fallback_screenshot_selection(tmp_path)
        assert result == [img]

    def test_excludes_empty_files(self, tmp_path):
        img = tmp_path / "after_01.png"
        img.write_bytes(b"")
        result = _fallback_screenshot_selection(tmp_path)
        assert result == []

    def test_returns_empty_when_no_pngs(self, tmp_path):
        result = _fallback_screenshot_selection(tmp_path)
        assert result == []

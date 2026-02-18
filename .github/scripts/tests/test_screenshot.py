"""Tests for screenshot module."""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.screenshot import (
    take_screenshot,
    embed_screenshots_markdown,
    _to_relative_path,
)
from lib.cline_runner import ClineError


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

        with patch("lib.screenshot.logger") as mock_logger:
            result = take_screenshot(mock_cline, output_path)
            # Should rename switch.png → before.png and return the path
            assert result == output_path
            assert output_path.exists()
            # Should log a warning mentioning the rename
            warning_calls = " ".join(
                str(c) for c in mock_logger.warning.call_args_list
            )
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

        md = embed_screenshots_markdown(before, [after1, after2], "ralph/issue-1", "user/repo")

        assert "Before" in md
        assert "After" in md
        assert "raw.githubusercontent.com" in md
        assert "ralph/issue-1" in md
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
    """Tests for _to_relative_path()."""

    def test_extracts_from_screenshots_dir(self):
        path = Path("/home/user/project/screenshots/before.png")
        assert _to_relative_path(path) == "screenshots/before.png"

    def test_falls_back_to_filename(self):
        path = Path("/home/user/project/images/before.png")
        assert _to_relative_path(path) == "before.png"

    def test_nested_screenshots_dir(self):
        path = Path("/home/user/project/screenshots/subdir/after.png")
        assert _to_relative_path(path) == "screenshots/subdir/after.png"

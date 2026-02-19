import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.utils import (
    load_prompt_template,
    screenshot_relative_path,
    read_visual_verdict,
)


class TestLoadPromptTemplate:
    def test_raises_when_file_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Prompt template not found"):
            load_prompt_template(tmp_path, "nonexistent.md")

    def test_returns_content_with_no_placeholders(self, tmp_path):
        (tmp_path / "prompt.md").write_text("Hello world", encoding="utf-8")
        result = load_prompt_template(tmp_path, "prompt.md")
        assert result == "Hello world"

    def test_substitutes_single_placeholder(self, tmp_path):
        (tmp_path / "prompt.md").write_text("Issue: {{ISSUE_NUMBER}}", encoding="utf-8")
        result = load_prompt_template(tmp_path, "prompt.md", ISSUE_NUMBER="42")
        assert result == "Issue: 42"

    def test_substitutes_multiple_placeholders(self, tmp_path):
        (tmp_path / "prompt.md").write_text("{{TITLE}} — {{BODY}}", encoding="utf-8")
        result = load_prompt_template(
            tmp_path, "prompt.md", TITLE="Fix bug", BODY="Details here"
        )
        assert result == "Fix bug — Details here"

    def test_non_string_value_is_stringified(self, tmp_path):
        (tmp_path / "prompt.md").write_text("Count: {{COUNT}}", encoding="utf-8")
        result = load_prompt_template(tmp_path, "prompt.md", COUNT=99)
        assert result == "Count: 99"

    def test_unreferenced_placeholder_stays_literal(self, tmp_path):
        (tmp_path / "prompt.md").write_text("{{UNUSED}}", encoding="utf-8")
        result = load_prompt_template(tmp_path, "prompt.md")
        assert result == "{{UNUSED}}"

    def test_multiple_occurrences_all_replaced(self, tmp_path):
        (tmp_path / "prompt.md").write_text("{{X}} and {{X}}", encoding="utf-8")
        result = load_prompt_template(tmp_path, "prompt.md", X="yes")
        assert result == "yes and yes"


class TestScreenshotRelativePath:
    def test_extracts_from_screenshots_dir(self):
        path = Path("/home/user/project/screenshots/before.png")
        assert screenshot_relative_path(path) == "screenshots/before.png"

    def test_falls_back_to_filename_when_no_screenshots_dir(self):
        path = Path("/home/user/project/images/before.png")
        assert screenshot_relative_path(path) == "before.png"

    def test_nested_path_under_screenshots(self):
        path = Path("/home/user/project/screenshots/run_1/after.png")
        assert screenshot_relative_path(path) == "screenshots/run_1/after.png"

    def test_screenshots_dir_at_root(self):
        path = Path("/screenshots/shot.png")
        assert screenshot_relative_path(path) == "screenshots/shot.png"


class TestReadVisualVerdict:
    def test_returns_none_when_file_missing(self, tmp_path):
        assert read_visual_verdict(tmp_path) is None

    def test_returns_content_when_file_exists(self, tmp_path):
        (tmp_path / "visual_verdict.txt").write_text(
            "VISUAL: OK\nSELECTED: after_01.png", encoding="utf-8"
        )
        result = read_visual_verdict(tmp_path)
        assert result == "VISUAL: OK\nSELECTED: after_01.png"

    def test_returns_none_when_file_is_empty(self, tmp_path):
        (tmp_path / "visual_verdict.txt").write_text("", encoding="utf-8")
        assert read_visual_verdict(tmp_path) is None

    def test_strips_surrounding_whitespace(self, tmp_path):
        (tmp_path / "visual_verdict.txt").write_text(
            "  VISUAL: OK  \n", encoding="utf-8"
        )
        result = read_visual_verdict(tmp_path)
        assert result == "VISUAL: OK"

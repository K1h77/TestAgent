"""Prompt template loading utilities.

Generic utilities for loading and substituting prompt templates.
No project-specific knowledge — works for any template directory.
"""

import os
from pathlib import Path


def get_default_prompts_dir() -> Path:
    """Return the bundled prompts directory.

    Checks RALPH_PROMPTS_DIR env var first, then falls back to the
    prompts/ directory bundled with the clanker package.
    """
    env = os.environ.get("RALPH_PROMPTS_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "prompts"


def load_prompt_template(prompts_dir: Path, name: str, **kwargs: str) -> str:
    """Load a prompt template file and substitute {{PLACEHOLDER}} values.

    Args:
        prompts_dir: Directory containing prompt templates.
        name: Filename of the template (e.g. 'tdd_prompt.md').
        **kwargs: Placeholder values to substitute (e.g. ISSUE_NUMBER="42").

    Returns:
        Template content with all specified placeholders substituted.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    path = prompts_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")

    content = path.read_text(encoding="utf-8")
    for key, value in kwargs.items():
        content = content.replace(f"{{{{{key}}}}}", str(value))

    return content

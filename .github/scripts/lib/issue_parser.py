"""Issue parsing and validation with fail-fast semantics.

Every field is validated. Missing or invalid data raises ValueError
immediately rather than allowing the agent to proceed with bad input.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Issue:
    """Parsed and validated GitHub issue."""

    number: int
    title: str
    body: str


def require_env(name: str) -> str:
    """Get a required environment variable or raise immediately.

    Args:
        name: Environment variable name.

    Returns:
        The value of the environment variable.

    Raises:
        ValueError: If the variable is missing or empty.
    """
    value = os.environ.get(name)
    if not value or not value.strip():
        raise ValueError(
            f"Required environment variable '{name}' is missing or empty. "
            f"Check your GitHub Actions workflow configuration."
        )
    return value.strip()


def parse_issue(number: str, title: str, body: str) -> Issue:
    """Parse and validate issue fields.

    Args:
        number: Issue number as string (from env var).
        title: Issue title.
        body: Issue body/description.

    Returns:
        Validated Issue dataclass.

    Raises:
        ValueError: If any field is missing, empty, or invalid.
    """
    # Validate number
    if not number or not number.strip():
        raise ValueError("Issue number is missing or empty.")

    try:
        issue_number = int(number.strip())
    except (ValueError, TypeError):
        raise ValueError(
            f"Issue number must be a positive integer, got: '{number}'"
        )

    if issue_number <= 0:
        raise ValueError(
            f"Issue number must be a positive integer, got: {issue_number}"
        )

    # Validate title
    if not title or not title.strip():
        raise ValueError(
            "Issue title is missing or empty. Cannot proceed without knowing "
            "what to fix."
        )

    # Validate body
    if not body or not body.strip():
        raise ValueError(
            "Issue body is missing or empty. Cannot proceed without a "
            "description of the problem."
        )

    return Issue(
        number=issue_number,
        title=title.strip(),
        body=body.strip(),
    )

"""Pydantic settings for environment variable validation.

Groups related env vars into typed settings classes. Pydantic-settings
reads from the process environment automatically and raises
ValidationError when required variables are missing or empty.
"""

from pydantic_settings import BaseSettings


class IssueSettings(BaseSettings):
    """GitHub issue metadata from environment."""

    issue_number: str
    issue_title: str
    issue_body: str
    issue_labels: str = ""


class ApiSettings(BaseSettings):
    """API credentials from environment."""

    openrouter_api_key: str


class ReviewSettings(BaseSettings):
    """Self-review inputs from environment (output of clanker_agent step)."""

    pr_number: str
    branch: str

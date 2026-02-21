"""Loader for .github/agent_config.yml.

Provides a single cached AgentConfig object with typed accessors so that
every script reads from the same central config file without redundant I/O.

Usage:
    from ralph.lib.agent_config import load_config

    cfg = load_config()
    cfg.models.coder_default       # "deepseek/deepseek-v3.2"
    cfg.models.coder_hard          # "minimax/minimax-m2.5"
    cfg.project.base_branch        # "main"
    cfg.project.test_command       # "npm test"
    cfg.retries.max_coding_attempts  # 3
    cfg.timeouts.coding_seconds      # 1800
"""

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ServerConfig(BaseModel):
    enabled: bool = False
    install_command: str = "npm ci"
    start_command: str = "node server.js"
    working_dir: str = "backend"
    port: int = 3000
    health_path: str = "/"


class ProjectConfig(BaseModel):
    base_branch: str = "main"
    test_command: str = "npm test"
    server: ServerConfig = Field(default_factory=ServerConfig)


class Models(BaseModel):
    coder_default: str  # Coder for non-hard tickets and early attempts (e.g. DeepSeek V3.2)
    coder_hard: str     # Coder for hard tickets + final attempt (e.g. MiniMax M2.5)
    planner_hard: str   # Planner for issues labelled "hard" (e.g. GLM-5)
    planner_default: str  # Planner for all other issues (e.g. DeepSeek V3.2)
    vision: str
    reviewer: str
    fixer: str


class Retries(BaseModel):
    max_coding_attempts: int
    max_review_iterations: int
    max_heal_attempts: int


class Timeouts(BaseModel):
    coding_seconds: int
    review_seconds: int
    fix_seconds: int
    screenshot_seconds: int
    test_seconds: int


class AgentConfig(BaseModel):
    models: Models
    retries: Retries
    timeouts: Timeouts
    project: ProjectConfig = Field(default_factory=ProjectConfig)


def _resolve_config_path() -> Path:
    env = os.environ.get("RALPH_CONFIG_PATH")
    if env:
        return Path(env)
    repo_root = Path(os.environ.get("RALPH_REPO_ROOT") or Path.cwd())
    candidate = repo_root / ".github" / "agent_config.yml"
    if candidate.exists():
        return candidate
    # fallback: script-relative path for local dev without env vars
    return Path(__file__).resolve().parent.parent.parent / ".github" / "agent_config.yml"


@lru_cache(maxsize=1)
def load_config(config_path: Optional[Path] = None) -> AgentConfig:
    """Load and parse agent_config.yml, caching the result.

    Args:
        config_path: Path to agent_config.yml. Defaults to auto-resolved location.

    Returns:
        Parsed AgentConfig with typed sub-objects.

    Raises:
        FileNotFoundError: If the config file does not exist.
        pydantic.ValidationError: If a required key is missing or has wrong type.
    """
    if config_path is None:
        config_path = _resolve_config_path()

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Agent config not found at {config_path}. "
            "Expected .github/agent_config.yml to exist in the repository root."
        )

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    logger.debug(f"Loaded agent config from {config_path}")

    return AgentConfig.model_validate(raw)

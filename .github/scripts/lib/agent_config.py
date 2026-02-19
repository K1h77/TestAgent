"""Loader for .github/agent_config.yml.

Provides a single cached AgentConfig object with typed accessors so that
every script reads from the same central config file without redundant I/O.

Usage:
    from lib.agent_config import load_config

    cfg = load_config()
    cfg.models.coder_default   # "deepseek/deepseek-v3.2"    (default coder)
    cfg.models.coder_hard      # "minimax/minimax-m2.5"      (hard tickets + final attempt)
    cfg.models.planner_hard    # "z-ai/glm-5"               (issues labelled "hard")
    cfg.models.planner_default # "deepseek/deepseek-v3.2"   (all other issues)
    cfg.retries.max_coding_attempts    # 3
    cfg.timeouts.coding_seconds        # 1800
"""

# TODO use pydantic settings instead of yaml parsing

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# Canonical location: .github/agent_config.yml
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "agent_config.yml"


@dataclass(frozen=True)
class Models:
    coder_default: (
        str  # Coder for non-hard tickets and early attempts (e.g. DeepSeek V3.2)
    )
    coder_hard: str  # Coder for hard tickets + final attempt (e.g. MiniMax M2.5)
    planner_hard: str  # Planner for issues labelled "hard" (e.g. GLM-5)
    planner_default: str  # Planner for all other issues (e.g. DeepSeek V3.2)
    vision: str
    reviewer: str
    fixer: str


@dataclass(frozen=True)
class Retries:
    max_coding_attempts: int
    max_review_iterations: int
    max_heal_attempts: int


@dataclass(frozen=True)
class Timeouts:
    coding_seconds: int
    review_seconds: int
    fix_seconds: int
    screenshot_seconds: int
    test_seconds: int


@dataclass(frozen=True)
class AgentConfig:
    models: Models
    retries: Retries
    timeouts: Timeouts


@lru_cache(maxsize=1)
def load_config(config_path: Path = _CONFIG_PATH) -> AgentConfig:
    """Load and parse agent_config.yml, caching the result.

    Args:
        config_path: Path to agent_config.yml. Defaults to the canonical location.

    Returns:
        Parsed AgentConfig with typed sub-objects.

    Raises:
        FileNotFoundError: If the config file does not exist.
        KeyError: If a required key is missing from the config file.
        ValueError: If a value has the wrong type.
    """
    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(
            f"Agent config not found at {config_path}. "
            "Expected .github/agent_config.yml to exist in the repository root."
        )

    with config_path.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    logger.debug(f"Loaded agent config from {config_path}")

    try:
        models = Models(
            coder_default=str(raw["models"]["coder_default"]),
            coder_hard=str(raw["models"]["coder_hard"]),
            planner_hard=str(raw["models"]["planner_hard"]),
            planner_default=str(raw["models"]["planner_default"]),
            vision=str(raw["models"]["vision"]),
            reviewer=str(raw["models"]["reviewer"]),
            fixer=str(raw["models"]["fixer"]),
        )
        retries = Retries(
            max_coding_attempts=int(raw["retries"]["max_coding_attempts"]),
            max_review_iterations=int(raw["retries"]["max_review_iterations"]),
            max_heal_attempts=int(raw["retries"]["max_heal_attempts"]),
        )
        timeouts = Timeouts(
            coding_seconds=int(raw["timeouts"]["coding_seconds"]),
            review_seconds=int(raw["timeouts"]["review_seconds"]),
            fix_seconds=int(raw["timeouts"]["fix_seconds"]),
            screenshot_seconds=int(raw["timeouts"]["screenshot_seconds"]),
            test_seconds=int(raw["timeouts"]["test_seconds"]),
        )
    except KeyError as e:
        raise KeyError(
            f"Missing required key in agent_config.yml: {e}. "
            "Check that agent_config.yml has all required fields."
        ) from e

    return AgentConfig(models=models, retries=retries, timeouts=timeouts)

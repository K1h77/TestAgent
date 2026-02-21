"""Tests for agent_config module — Pydantic models and ProjectConfig/ServerConfig."""

import pytest
from pathlib import Path

from clanker.lib.agent_config import (
    load_config,
    AgentConfig,
    Models,
    Retries,
    Timeouts,
    ProjectConfig,
    ServerConfig,
)

_VALID_MODELS_YAML = """\
models:
  coder_default: "deepseek/deepseek-v3.2"
  coder_hard: "minimax/minimax-m2.5"
  planner_hard: "z-ai/glm-5"
  planner_default: "deepseek/deepseek-v3.2"
  vision: "moonshotai/kimi-k2.5"
  reviewer: "z-ai/glm-5"
  fixer: "deepseek/deepseek-v3.2"
retries:
  max_coding_attempts: 3
  max_review_iterations: 3
  max_heal_attempts: 3
timeouts:
  coding_seconds: 1800
  review_seconds: 600
  fix_seconds: 600
  screenshot_seconds: 600
  test_seconds: 120
"""


class TestServerConfig:
    def test_defaults(self):
        cfg = ServerConfig()
        assert cfg.enabled is False
        assert cfg.install_command == "npm ci"
        assert cfg.start_command == "node server.js"
        assert cfg.working_dir == "backend"
        assert cfg.port == 3000
        assert cfg.health_path == "/"

    def test_custom_values(self):
        cfg = ServerConfig(enabled=True, port=8080, working_dir="app")
        assert cfg.enabled is True
        assert cfg.port == 8080
        assert cfg.working_dir == "app"

    def test_port_type_coercion(self):
        cfg = ServerConfig(port="9000")
        assert cfg.port == 9000
        assert isinstance(cfg.port, int)


class TestProjectConfig:
    def test_defaults(self):
        cfg = ProjectConfig()
        assert cfg.base_branch == "main"
        assert cfg.test_command == "npm test"
        assert isinstance(cfg.server, ServerConfig)

    def test_custom_values(self):
        cfg = ProjectConfig(base_branch="develop", test_command="pytest -x")
        assert cfg.base_branch == "develop"
        assert cfg.test_command == "pytest -x"

    def test_nested_server_config(self):
        cfg = ProjectConfig(server=ServerConfig(port=4000, enabled=True))
        assert cfg.server.port == 4000
        assert cfg.server.enabled is True


class TestLoadConfig:
    def test_valid_config_without_project_section(self, tmp_path):
        """Config without project section uses defaults for ProjectConfig."""
        config = tmp_path / "agent_config.yml"
        config.write_text(_VALID_MODELS_YAML)

        cfg = load_config(config)
        assert cfg.project.base_branch == "main"
        assert cfg.project.test_command == "npm test"
        assert cfg.project.server.port == 3000
        assert cfg.project.server.enabled is False

    def test_valid_config_with_project_section(self, tmp_path):
        """Config with project section is parsed correctly."""
        config = tmp_path / "agent_config.yml"
        config.write_text(
            _VALID_MODELS_YAML
            + """\
project:
  base_branch: "develop"
  test_command: "pytest -x"
  server:
    enabled: true
    port: 8080
    working_dir: "app"
"""
        )

        cfg = load_config(config)
        assert cfg.project.base_branch == "develop"
        assert cfg.project.test_command == "pytest -x"
        assert cfg.project.server.enabled is True
        assert cfg.project.server.port == 8080
        assert cfg.project.server.working_dir == "app"

    def test_missing_required_model_field_raises(self, tmp_path):
        """Missing required model field raises ValidationError."""
        from pydantic import ValidationError

        config = tmp_path / "agent_config.yml"
        config.write_text("""\
models:
  coder_default: "deepseek/deepseek-v3.2"
  # coder_hard missing
retries:
  max_coding_attempts: 3
  max_review_iterations: 3
  max_heal_attempts: 3
timeouts:
  coding_seconds: 1800
  review_seconds: 600
  fix_seconds: 600
  screenshot_seconds: 600
  test_seconds: 120
""")
        with pytest.raises(ValidationError):
            load_config(config)

    def test_file_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yml")

    def test_models_parsed_correctly(self, tmp_path):
        config = tmp_path / "agent_config.yml"
        config.write_text(_VALID_MODELS_YAML)

        cfg = load_config(config)
        assert cfg.models.coder_default == "deepseek/deepseek-v3.2"
        assert cfg.models.coder_hard == "minimax/minimax-m2.5"
        assert cfg.models.planner_hard == "z-ai/glm-5"
        assert cfg.models.reviewer == "z-ai/glm-5"
        assert cfg.models.fixer == "deepseek/deepseek-v3.2"

    def test_retries_and_timeouts_parsed(self, tmp_path):
        config = tmp_path / "agent_config.yml"
        config.write_text(_VALID_MODELS_YAML)

        cfg = load_config(config)
        assert cfg.retries.max_coding_attempts == 3
        assert cfg.retries.max_review_iterations == 3
        assert cfg.retries.max_heal_attempts == 3
        assert cfg.timeouts.coding_seconds == 1800
        assert cfg.timeouts.test_seconds == 120

    def test_returns_agent_config_instance(self, tmp_path):
        config = tmp_path / "agent_config.yml"
        config.write_text(_VALID_MODELS_YAML)

        cfg = load_config(config)
        assert isinstance(cfg, AgentConfig)
        assert isinstance(cfg.models, Models)
        assert isinstance(cfg.retries, Retries)
        assert isinstance(cfg.timeouts, Timeouts)
        assert isinstance(cfg.project, ProjectConfig)

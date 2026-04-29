"""
Configuration management for the game.

"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator
from game.utils.logger import get_logger

logger = get_logger(__name__)

class ConfigurationError(RuntimeError):
    """Raised when configuration cannot be loaded or validated."""


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML data from the provided path."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Failed to parse configuration file at {path}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise ConfigurationError(
            f"Configuration file at {path} must contain a top-level mapping."
        )

    return data


class GameSettingsModel(BaseModel):

    min_players: int = Field(default=3, ge=1)
    max_players: int = Field(default=10, ge=1)
    max_rounds: int = Field(default=8, ge=1)

    @model_validator(mode="after")
    def validate_limits(self) -> "GameSettingsModel":
        if self.min_players > self.max_players:
            raise ValueError("min_players cannot exceed max_players")
        return self


class GameModel(BaseModel):

    player_count: int = Field(default=6, ge=4, le=10)
    vocabulary: List[Tuple[str, str]] = Field(default_factory=list)
    player_names: List[str] = Field(default_factory=list)
    settings: GameSettingsModel = Field(default_factory=GameSettingsModel)

    @model_validator(mode="after")
    def validate_game(self) -> "GameModel":
        if not self.vocabulary:
            raise ValueError("Vocabulary list cannot be empty")
        for entry in self.vocabulary:
            if len(entry) != 2 or any(
                not isinstance(word, str) or not word for word in entry
            ):
                raise ValueError(
                    "Each vocabulary pair must contain two non-empty strings"
                )

        unique_names = set(self.player_names)
        if len(unique_names) != len(self.player_names):
            raise ValueError("Player names must be unique")
        if len(self.player_names) < self.player_count:
            raise ValueError(
                "Player name pool is smaller than the configured player count"
            )

        if (
            not self.settings.min_players
            <= self.player_count
            <= self.settings.max_players
        ):
            raise ValueError(
                "player_count must be between min_players and max_players (inclusive)"
            )
        return self


class MetricsConfigModel(BaseModel):
    """Configuration for optional metrics collection."""

    enabled: bool = False


class ProjectConfigModel(BaseModel):
    """Top-level Pydantic model for project configuration."""

    game: GameModel = Field(default_factory=GameModel)
    metrics: MetricsConfigModel = Field(default_factory=MetricsConfigModel)


class GameConfig:

    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize configuration.

        Args:
            config_path: Path to YAML configuration file. If None, uses defaults.
        """
        self.config_path = Path(config_path).expanduser() if config_path else None
        self._config = self._load_config()

    def _load_config(self) -> ProjectConfigModel:
        """Load configuration from file, merge with defaults, and validate."""

        user_config = _load_yaml(self.config_path)

        try:
            return ProjectConfigModel.model_validate(user_config)
        except ValidationError as exc:
            detail = exc.errors()
            location = self.config_path or "built-in defaults"
            raise ConfigurationError(
                f"Invalid configuration in {location}: {detail}"
            ) from exc

    @property
    def player_count(self) -> int:
        """Get the configured number of players."""
        return self._config.game.player_count

    @property
    def vocabulary(self) -> List[Tuple[str, str]]:
        """Get the vocabulary list."""
        return [tuple(pair) for pair in self._config.game.vocabulary]

    @property
    def player_names_pool(self) -> List[str]:
        """Get the pool of available player names."""
        return list(self._config.game.player_names)

    @property
    def max_rounds(self) -> int:
        """Get the maximum number of rounds per game."""
        return self._config.game.settings.max_rounds

    @property
    def metrics_enabled(self) -> bool:
        """Return whether metrics collection is enabled."""
        return self._config.metrics.enabled

    def get_game_rules(self) -> dict:
        """
        Get game rules for LLM interactions.
        Returns a dict compatible with the old PUBLIC_RULES format.
        """
        return {
            "max_rounds": self.max_rounds,
            "spy_count": calculate_spy_count(self.player_count),
        }

    def generate_player_names(self) -> List[str]:
        """
        Generate player names based on configured player count.
        Returns consistent results by selecting names in order.
        """
        count = self.player_count
        available_names = self.player_names_pool

        if count > len(available_names):
            raise ValueError(
                f"Cannot generate {count} unique names from pool of {len(available_names)} names"
            )

        return available_names[:count]


def default_config_path() -> Path:
    """Return the default config file location inside the repository."""
    return Path(__file__).resolve().parents[2] / "config.yaml"


def load_config(config_path: str | Path | None = None) -> GameConfig:
    """
    Build a new GameConfig instance from the provided path.

    Args:
        config_path: default use ``config.yaml`` at the project root.
    """
    resolved_path = (
        Path(config_path).expanduser() if config_path else default_config_path()
    )
    return GameConfig(resolved_path)


def calculate_spy_count(total_players: int) -> int:
    """
    Calculate the number of spies based on total players.
    """
    if total_players <= 4:
        return 1
    elif total_players <= 6:
        return 2
    elif total_players <= 8:
        return 2
    elif total_players <= 10:
        return 3
    else:
        return min(4, total_players // 3)

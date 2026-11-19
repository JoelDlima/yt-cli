"""Persistent settings management.

Loads, saves, validates, and resets application settings stored as JSON
at ``~/.ytdownloader/config.json``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ytdownloader.constants import CONFIG_PATH
from ytdownloader.exceptions import ConfigError
from ytdownloader.logger import get_logger
from ytdownloader.models import Settings
from ytdownloader.storage import read_json, write_json

logger = get_logger()

_ENV_FIELD_MAP: dict[str, str] = {
    "YTDL_OUTPUT_DIR": "output_dir",
    "YTDL_COOKIE_FILE": "cookie_file",
    "YTDL_PROXY": "proxy",
    "YTDL_RATE_LIMIT": "rate_limit",
}


def load_dotenv_if_available() -> None:
    """Load variables from a local ``.env`` file if ``python-dotenv`` is installed."""
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(override=False)
    except Exception:
        pass


def get_env_overrides() -> dict[str, Any]:
    """Return non-empty ``YTDL_*`` environment variable overrides for :class:`Settings`."""
    load_dotenv_if_available()
    overrides: dict[str, Any] = {}
    for env_key, field_name in _ENV_FIELD_MAP.items():
        value = os.environ.get(env_key, "").strip()
        if value:
            overrides[field_name] = value
    return overrides


class ConfigManager:
    """Manages loading, saving, and validating persisted :class:`Settings`."""

    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path
        self._settings: Settings | None = None

    def load(self) -> Settings:
        """Load settings from disk, falling back to environment overrides and defaults."""
        if self._settings is not None:
            return self._settings

        env_overrides = get_env_overrides()
        raw = read_json(self.path, default=None)
        if raw is None:
            self._settings = Settings(**env_overrides)
            self.save(self._settings)
            return self._settings

        default_dump = Settings().model_dump()
        merged = dict(raw)
        for field_name, env_val in env_overrides.items():
            if merged.get(field_name) in (None, "", default_dump.get(field_name)):
                merged[field_name] = env_val

        try:
            self._settings = Settings(**merged)
        except ValidationError as exc:
            logger.warning("Invalid config detected, resetting to defaults: %s", exc)
            self._settings = Settings(**env_overrides)
            self.save(self._settings)

        return self._settings

    def save(self, settings: Settings) -> None:
        """Persist ``settings`` to disk."""
        try:
            write_json(self.path, settings.model_dump())
            self._settings = settings
        except OSError as exc:
            raise ConfigError(f"Could not save settings to {self.path}") from exc

    def update(self, **kwargs: Any) -> Settings:
        """Update one or more settings fields and persist the result."""
        current = self.load()
        data = current.model_dump()
        data.update(kwargs)
        try:
            updated = Settings(**data)
        except ValidationError as exc:
            raise ConfigError(f"Invalid setting value: {exc}") from exc
        self.save(updated)
        return updated

    def reset(self) -> Settings:
        """Reset settings to application defaults."""
        defaults = Settings()
        self.save(defaults)
        return defaults

    def export(self, dest: Path) -> None:
        """Export current settings to ``dest``."""
        write_json(dest, self.load().model_dump())

    def import_from(self, src: Path) -> Settings:
        """Import settings from ``src``, validating before applying."""
        raw = read_json(src, default=None)
        if raw is None:
            raise ConfigError(f"Could not read config file {src}")
        try:
            settings = Settings(**raw)
        except ValidationError as exc:
            raise ConfigError(f"Imported config is invalid: {exc}") from exc
        self.save(settings)
        return settings

    def validate_integrity(self) -> tuple[bool, str | None]:
        """Validate the current config file. Returns (is_valid, error_message)."""
        raw = read_json(self.path, default=None)
        if raw is None:
            return False, "Config file missing or unreadable."
        try:
            Settings(**raw)
        except ValidationError as exc:
            return False, str(exc)
        return True, None


_config_manager: ConfigManager | None = None


def get_config_manager() -> ConfigManager:
    """Return the process-wide :class:`ConfigManager` singleton."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

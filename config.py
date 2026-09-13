from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "config.json"
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

if not CONFIG_PATH.is_file():
    raise RuntimeError(f"Unable to load configuration file: {CONFIG_PATH}")

with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
    config: dict[str, Any] = json.load(config_file)


def _branding_value(key: str, default: str) -> str:
    branding = config.get("branding", {}) if isinstance(config.get("branding"), dict) else {}
    value = str(branding.get(key) or default).strip()
    return value or default


BRAND_NAME = _branding_value("name", "SpryteAI")
CREATOR_NAME = _branding_value("creator", "DJ BlakSpryte")


def _set_from_env(path: tuple[str, ...], env_name: str) -> None:
    value = os.getenv(env_name)
    if value is None or value == "":
        return

    target: dict[str, Any] = config
    for key in path[:-1]:
        target = target.setdefault(key, {})
    target[path[-1]] = value


# Secrets and deployment-specific values should be supplied via environment variables.
_ENV_OVERRIDES: dict[tuple[str, ...], str] = {
    ("bot", "token"): "DISCORD_TOKEN",
    ("bot", "webhook_url"): "SPRYTEAI_WEBHOOK_URL",
    ("database", "host"): "DATABASE_HOST",
    ("database", "database"): "DATABASE_NAME",
    ("database", "user"): "DATABASE_USER",
    ("database", "password"): "DATABASE_PASSWORD",
    ("reddit", "client_id"): "REDDIT_CLIENT_ID",
    ("reddit", "client_secret"): "REDDIT_CLIENT_SECRET",
    ("twitch", "client_id"): "TWITCH_CLIENT_ID",
    ("twitch", "client_secret"): "TWITCH_CLIENT_SECRET",
    ("twitch", "redirect_uri"): "TWITCH_REDIRECT_URI",
}

for config_path, environment_name in _ENV_OVERRIDES.items():
    _set_from_env(config_path, environment_name)


def require_config(path: tuple[str, ...], *, label: str | None = None) -> Any:
    value: Any = config
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
        if value is None:
            break

    if value in (None, ""):
        display_name = label or ".".join(path)
        raise RuntimeError(f"Missing required configuration value: {display_name}")
    return value

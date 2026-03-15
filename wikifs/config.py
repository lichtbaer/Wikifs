"""TOML configuration loader with default values."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load configuration from TOML file, merging with defaults."""
    defaults: dict[str, Any] = {
        "wikifs": {
            "default_language": "de",
            "supported_languages": ["de", "en"],
        },
        "cache": {
            "l1_max_size": 256,
            "l1_ttl_seconds": 3600,
            "l2_ttl_seconds": 86400,
            "l2_db_path": "~/.wikifs/cache.db",
        },
        "tracing": {
            "enabled": True,
            "db_path": "~/.wikifs/traces.db",
        },
        "api": {
            "wikidata_base_url": "https://www.wikidata.org",
            "wikipedia_base_url": "https://{lang}.wikipedia.org",
            "request_timeout_seconds": 10,
            "user_agent": "WikiFS/0.1 (https://github.com/Lichtbaer/wikifs)",
        },
        "pagination": {
            "default_limit": 100,
            "max_limit": 500,
        },
    }

    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config.toml"

    path = Path(config_path)
    if not path.exists():
        return defaults

    with path.open("rb") as f:
        loaded = tomllib.load(f)

    def merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        result = dict(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge(result[key], value)
            else:
                result[key] = value
        return result

    return merge(defaults, loaded)

"""TOML configuration loader with default values."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ApiConfig:
    """API configuration for Wikidata and Wikipedia clients."""

    wikidata_base_url: str
    wikipedia_base_url: str
    request_timeout_seconds: int
    user_agent: str

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> ApiConfig:
        """Create ApiConfig from loaded config dict."""
        api = config.get("api", {})
        return cls(
            wikidata_base_url=str(api.get("wikidata_base_url", "https://www.wikidata.org")),
            wikipedia_base_url=str(api.get("wikipedia_base_url", "https://{lang}.wikipedia.org")),
            request_timeout_seconds=int(api.get("request_timeout_seconds", 10)),
            user_agent=str(api.get("user_agent", "WikiFS/0.1 (https://github.com/Lichtbaer/wikifs)")),
        )


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
        "agent": {
            "default_model": "openai:gpt-4o",
            "max_tool_calls": 20,
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

    result = merge(defaults, loaded)

    # Docker / container: override DB paths via WIKIFS_DATA_DIR
    data_dir = os.environ.get("WIKIFS_DATA_DIR")
    if data_dir:
        result.setdefault("cache", {})["l2_db_path"] = str(Path(data_dir) / "cache.db")
        result.setdefault("tracing", {})["db_path"] = str(Path(data_dir) / "traces.db")

    return result

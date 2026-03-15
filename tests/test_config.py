"""Tests for config loading."""

from __future__ import annotations

import tempfile
from pathlib import Path

from wikifs.config import load_config


def test_load_config_default_values() -> None:
    """Config loading returns default values when no config file exists."""
    config = load_config(config_path=Path("/nonexistent/config.toml"))
    assert config["wikifs"]["default_language"] == "de"
    assert config["wikifs"]["supported_languages"] == ["de", "en"]
    assert config["cache"]["l1_max_size"] == 256
    assert config["cache"]["l1_ttl_seconds"] == 3600
    assert config["cache"]["l2_ttl_seconds"] == 86400
    assert config["cache"]["l2_db_path"] == "~/.wikifs/cache.db"
    assert config["tracing"]["enabled"] is True
    assert config["tracing"]["db_path"] == "~/.wikifs/traces.db"
    assert config["api"]["wikidata_base_url"] == "https://www.wikidata.org"
    assert config["api"]["wikipedia_base_url"] == "https://{lang}.wikipedia.org"
    assert config["api"]["request_timeout_seconds"] == 10
    assert config["pagination"]["default_limit"] == 100
    assert config["pagination"]["max_limit"] == 500


def test_load_config_custom_values() -> None:
    """Config loading merges custom values from TOML file."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
        f.write(
            b"""[wikifs]
default_language = "en"
supported_languages = ["en", "fr"]

[cache]
l1_max_size = 512

[pagination]
default_limit = 50
"""
        )
        config_path = Path(f.name)

    try:
        config = load_config(config_path=config_path)
        assert config["wikifs"]["default_language"] == "en"
        assert config["wikifs"]["supported_languages"] == ["en", "fr"]
        assert config["cache"]["l1_max_size"] == 512
        assert config["cache"]["l1_ttl_seconds"] == 3600  # unchanged default
        assert config["pagination"]["default_limit"] == 50
        assert config["pagination"]["max_limit"] == 500  # unchanged default
    finally:
        config_path.unlink()

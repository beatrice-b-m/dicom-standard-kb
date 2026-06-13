from __future__ import annotations

from pathlib import Path

import pytest

from dicom_kb.config import (
    ConfigError,
    bool_env,
    int_env,
    load_config_profile,
    path_env,
    sqlite_url_path,
    str_env,
    value_with_precedence,
)


def test_load_config_profile_accepts_section17_shape(tmp_path: Path) -> None:
    path = tmp_path / "dicom-kb.yaml"
    path.write_text(
        """
        dicom_kb:
          edition: "2026b"
          artifact_dir: "~/dicom/artifacts"
          database_url: "sqlite:///~/dicom/db/2026b.sqlite"
          allow_text_retrieval: true
          max_text_excerpt_chars: 1200
          require_citations: true
          require_edition_pin: true
          allow_network_fetch: false
          use_synthetic_fixtures_only: true
          require_dicom_download_for_integration: false
          publish_generated_db: false
        """,
        encoding="utf-8",
    )

    config = load_config_profile(path)

    assert config.edition == "2026b"
    assert config.artifact_dir == Path("~/dicom/artifacts")
    assert config.database_url == "sqlite:///~/dicom/db/2026b.sqlite"
    assert config.max_text_excerpt_chars == 1200
    assert config.require_citations is True
    assert config.publish_generated_db is False


def test_load_config_profile_accepts_public_ci_shape(tmp_path: Path) -> None:
    path = tmp_path / "dicom-kb-ci.yaml"
    path.write_text(
        """
        dicom_kb:
          allow_text_retrieval: false
          use_synthetic_fixtures_only: true
          require_dicom_download_for_integration: true
          publish_generated_db: false
        """,
        encoding="utf-8",
    )

    config = load_config_profile(path)

    assert config.allow_text_retrieval is False
    assert config.use_synthetic_fixtures_only is True
    assert config.require_dicom_download_for_integration is True
    assert config.publish_generated_db is False


def test_load_config_profile_rejects_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "dicom-kb.yaml"
    path.write_text(
        """
        dicom_kb:
          edition: "2026b"
          unexpected: true
        """,
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="unexpected"):
        load_config_profile(path)


def test_load_config_profile_rejects_invalid_yaml(tmp_path: Path) -> None:
    path = tmp_path / "dicom-kb.yaml"
    path.write_text("dicom_kb: [", encoding="utf-8")

    with pytest.raises(ConfigError, match="invalid YAML config"):
        load_config_profile(path)


def test_load_config_profile_rejects_invalid_database_url(tmp_path: Path) -> None:
    path = tmp_path / "dicom-kb.yaml"
    path.write_text(
        """
        dicom_kb:
          database_url: "postgresql:///dicom"
        """,
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="sqlite:///"):
        load_config_profile(path)


def test_load_config_profile_rejects_disabled_citations(tmp_path: Path) -> None:
    path = tmp_path / "dicom-kb.yaml"
    path.write_text(
        """
        dicom_kb:
          require_citations: false
        """,
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="citation requirements"):
        load_config_profile(path)


def test_precedence_prefers_cli_then_env_then_config_then_default() -> None:
    assert (
        value_with_precedence(
            cli_value="cli",
            env_value="env",
            config_value="config",
            default="default",
        )
        == "cli"
    )
    assert (
        value_with_precedence(
            cli_value=None,
            env_value="env",
            config_value="config",
            default="default",
        )
        == "env"
    )
    assert (
        value_with_precedence(
            cli_value=None,
            env_value=None,
            config_value="config",
            default="default",
        )
        == "config"
    )
    assert (
        value_with_precedence(
            cli_value=None,
            env_value=None,
            config_value=None,
            default="default",
        )
        == "default"
    )


def test_sqlite_url_path_supports_only_local_sqlite_urls() -> None:
    assert sqlite_url_path("sqlite:////tmp/dicom.sqlite") == Path("/tmp/dicom.sqlite")
    with pytest.raises(ConfigError, match="sqlite:///"):
        sqlite_url_path("postgresql:///dicom")
    with pytest.raises(ConfigError, match="sqlite:///"):
        sqlite_url_path("sqlite://server/dicom.sqlite")


def test_environment_helpers_parse_values() -> None:
    environ = {
        "DICOM_KB_CACHE_DIR": "/tmp/cache",
        "DICOM_KB_EDITION": "2026b",
        "DICOM_KB_ALLOW_TEXT": "yes",
        "DICOM_KB_MAX_CHARS": "800",
    }

    assert path_env(environ, "DICOM_KB_CACHE_DIR") == Path("/tmp/cache")
    assert str_env(environ, "DICOM_KB_EDITION") == "2026b"
    assert bool_env(environ, "DICOM_KB_ALLOW_TEXT") is True
    assert int_env(environ, "DICOM_KB_MAX_CHARS") == 800
    with pytest.raises(ConfigError, match="boolean"):
        bool_env({"FLAG": "sometimes"}, "FLAG")
    with pytest.raises(ConfigError, match="integer"):
        int_env({"COUNT": "many"}, "COUNT")

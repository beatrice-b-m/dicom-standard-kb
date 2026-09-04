"""YAML configuration profile loading."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConfigError(ValueError):
    """Raised when a configuration profile is invalid."""


class DicomKBConfig(BaseModel):
    """Typed config profile under the top-level `dicom_kb` key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edition: str | None = None
    artifact_dir: Path | None = None
    database_url: str | None = None
    allow_text_retrieval: bool | None = None
    max_text_excerpt_chars: int | None = Field(default=None, ge=1)
    require_citations: bool | None = None
    require_edition_pin: bool | None = None
    allow_network_fetch: bool | None = None
    use_synthetic_fixtures_only: bool | None = None
    require_dicom_download_for_integration: bool | None = None
    publish_generated_db: bool | None = None

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = urlparse(value)
        if parsed.scheme != "sqlite":
            raise ValueError("database_url must use sqlite:/// in v1")
        if not value.startswith("sqlite:///"):
            raise ValueError("database_url must use sqlite:/// in v1")
        return value

    @field_validator("require_citations")
    @classmethod
    def _require_citations_cannot_be_disabled(cls, value: bool | None) -> bool | None:
        if value is False:
            raise ValueError("config files cannot disable citation requirements")
        return value


class ConfigProfile(BaseModel):
    """Top-level YAML config envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dicom_kb: DicomKBConfig


def load_config_profile(path: Path) -> DicomKBConfig:
    """Load and validate a YAML configuration profile."""
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML config: {exc}") from exc
    except OSError as exc:
        raise ConfigError(f"could not read config: {path}") from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, Mapping):
        raise ConfigError("config must be a YAML mapping")
    try:
        return ConfigProfile.model_validate(raw).dicom_kb
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc


def value_with_precedence[T](
    *,
    cli_value: T | None,
    env_value: T | None,
    config_value: T | None,
    default: T,
) -> T:
    """Resolve CLI > environment > config > default precedence."""
    if cli_value is not None:
        return cli_value
    if env_value is not None:
        return env_value
    if config_value is not None:
        return config_value
    return default


def sqlite_url_path(database_url: str) -> Path:
    """Return a filesystem path from a validated sqlite:/// URL."""
    parsed = urlparse(database_url)
    if parsed.scheme != "sqlite" or not database_url.startswith("sqlite:///"):
        raise ConfigError("database_url must use sqlite:/// in v1")
    if parsed.netloc:
        raise ConfigError("database_url must use a local sqlite:/// path")
    path = parsed.path
    if path.startswith("//"):
        path = path[1:]
    return Path(path).expanduser()


def path_env(environ: Mapping[str, str], name: str) -> Path | None:
    """Read an optional path-like environment variable."""
    value = environ.get(name)
    return Path(value).expanduser() if value else None


def str_env(environ: Mapping[str, str], name: str) -> str | None:
    """Read an optional string environment variable."""
    return environ.get(name) or None


def bool_env(environ: Mapping[str, str], name: str) -> bool | None:
    """Read an optional boolean environment variable."""
    value = environ.get(name)
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be a boolean value")


def int_env(environ: Mapping[str, str], name: str) -> int | None:
    """Read an optional integer environment variable."""
    value = environ.get(name)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc

"""YAML configuration profile loading."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, field_validator


class ConfigError(ValueError):
    """Raised when a configuration profile is invalid."""


class DicomKBConfig(BaseModel):
    """Typed config profile under the top-level `dicom_kb` key."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edition: str | None = None
    artifact_dir: Path | None = None
    database_url: str | None = None

    @field_validator("artifact_dir")
    @classmethod
    def _expand_artifact_dir(cls, value: Path | None) -> Path | None:
        return value.expanduser() if value is not None else None

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
    """Return the file a sqlite:/// URL names.

    As in SQLAlchemy, everything after `sqlite:///` is the path as written:
    `sqlite:////data/kb.sqlite` is absolute, `sqlite:///kb.sqlite` is relative,
    and `sqlite:///~/kb.sqlite` is under the home directory.
    """
    if not database_url.startswith("sqlite:///"):
        raise ConfigError("database_url must use sqlite:/// in v1")
    path = database_url.removeprefix("sqlite:///")
    if not path:
        raise ConfigError("database_url must name a file after sqlite:///")
    return Path(path).expanduser()


def path_env(environ: Mapping[str, str], name: str) -> Path | None:
    """Read an optional path-like environment variable."""
    value = environ.get(name)
    return Path(value).expanduser() if value else None


def str_env(environ: Mapping[str, str], name: str) -> str | None:
    """Read an optional string environment variable."""
    return environ.get(name) or None

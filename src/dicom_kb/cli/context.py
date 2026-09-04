"""Invocation configuration, query connections, and JSON output."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import AbstractContextManager
from pathlib import Path

import typer
from pydantic import BaseModel

from dicom_kb.build import (
    default_db_path,
)
from dicom_kb.config import (
    DicomKBConfig,
    int_env,
    path_env,
    sqlite_url_path,
    str_env,
    value_with_precedence,
)
from dicom_kb.db.models import read_sqlite
from dicom_kb.query.answer_contracts import ToolResponse
from dicom_kb.sources.downloader import (
    DEFAULT_CACHE_DIR,
)


def resolve_edition(
    ctx: typer.Context, cli_value: str | None, *, default: str | None = None
) -> str:
    resolved = value_with_precedence(
        cli_value=cli_value,
        env_value=str_env(os.environ, "DICOM_KB_EDITION"),
        config_value=_active_config(ctx).edition,
        default=default,
    )
    if resolved is None:
        raise typer.BadParameter(
            "--edition is required when not supplied by environment or config"
        )
    return resolved


def resolve_cache_dir(ctx: typer.Context, cli_value: Path | None) -> Path:
    return value_with_precedence(
        cli_value=cli_value,
        env_value=path_env(os.environ, "DICOM_KB_CACHE_DIR"),
        config_value=_active_config(ctx).artifact_dir,
        default=DEFAULT_CACHE_DIR,
    )


def resolve_db_path(ctx: typer.Context, cli_value: Path | None) -> Path | None:
    if cli_value is not None:
        return cli_value
    env_database_url = str_env(os.environ, "DICOM_KB_DATABASE_URL")
    if env_database_url is not None:
        return sqlite_url_path(env_database_url)
    database_url = _active_config(ctx).database_url
    if database_url is not None:
        return sqlite_url_path(database_url)
    return None


def resolve_max_text_chars(
    ctx: typer.Context, cli_value: int | None, *, default: int
) -> int:
    return value_with_precedence(
        cli_value=cli_value,
        env_value=int_env(os.environ, "DICOM_KB_MAX_TEXT_EXCERPT_CHARS"),
        config_value=_active_config(ctx).max_text_excerpt_chars,
        default=default,
    )


def connect_query_db(
    path: Path | None, *, cache_dir: Path, edition: str
) -> AbstractContextManager[sqlite3.Connection]:
    resolved = path if path is not None else default_db_path(cache_dir, edition)
    if not resolved.is_file():
        raise typer.BadParameter(f"SQLite KB does not exist: {resolved}")
    return read_sqlite(resolved)


def echo_response(response: ToolResponse) -> None:
    payload = response.model_dump(mode="json", exclude_none=True)
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


def json_model(model: BaseModel) -> str:
    return json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)


def _active_config(ctx: typer.Context) -> DicomKBConfig:
    """Read configuration owned by the current CLI invocation."""
    config = ctx.find_object(DicomKBConfig)
    if config is None:
        raise RuntimeError("CLI configuration context was not initialized")
    return config

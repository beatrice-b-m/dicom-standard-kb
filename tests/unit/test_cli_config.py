from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from dicom_kb.cli.main import app


def test_cli_config_supplies_build_fixture_defaults(tmp_path: Path) -> None:
    cache_dir = tmp_path / "profile-cache"
    db_path = tmp_path / "profile.sqlite"
    config_path = _config_file(
        tmp_path,
        edition="2026c",
        cache_dir=cache_dir,
        db_path=db_path,
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "build-fixture", "--force"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["edition"] == "2026c"
    assert payload["db_path"] == str(db_path)
    assert (cache_dir / "artifacts/2026c/manifest.json").exists()


def test_cli_config_supplies_query_defaults(tmp_path: Path) -> None:
    cache_dir = tmp_path / "profile-cache"
    db_path = tmp_path / "profile.sqlite"
    config_path = _config_file(
        tmp_path,
        edition="2026c",
        cache_dir=cache_dir,
        db_path=db_path,
    )
    build_result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "build-fixture", "--force"],
    )
    assert build_result.exit_code == 0, build_result.output

    lookup_result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "lookup", "tag", "Modality"],
    )

    assert lookup_result.exit_code == 0, lookup_result.output
    payload = json.loads(lookup_result.output)
    assert payload["edition"] == "2026c"
    assert payload["status"] == "ok"
    assert payload["result"]["keyword"] == "Modality"


def test_cli_flags_override_config_defaults(tmp_path: Path) -> None:
    profile_cache = tmp_path / "profile-cache"
    profile_db = tmp_path / "profile.sqlite"
    cli_cache = tmp_path / "cli-cache"
    cli_db = tmp_path / "cli.sqlite"
    config_path = _config_file(
        tmp_path,
        edition="2026c",
        cache_dir=profile_cache,
        db_path=profile_db,
    )

    result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "build-fixture",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cli_cache),
            "--db",
            str(cli_db),
            "--force",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["edition"] == "2026b"
    assert payload["db_path"] == str(cli_db)
    assert (cli_cache / "artifacts/2026b/manifest.json").exists()
    assert not (profile_cache / "artifacts/2026c/manifest.json").exists()


def _config_file(
    tmp_path: Path, *, edition: str, cache_dir: Path, db_path: Path
) -> Path:
    path = tmp_path / "dicom-kb.yaml"
    path.write_text(
        f"""
        dicom_kb:
          edition: "{edition}"
          artifact_dir: "{cache_dir}"
          database_url: "sqlite:///{db_path}"
          require_citations: true
        """,
        encoding="utf-8",
    )
    return path

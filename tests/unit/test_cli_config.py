from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from dicom_kb.cli.main import app
from tests.fixtures_synthetic import EDITION, OTHER_EDITION


def test_cli_config_supplies_build_fixture_paths(tmp_path: Path) -> None:
    cache_dir = tmp_path / "profile-cache"
    db_path = tmp_path / "profile.sqlite"
    config_path = _config_file(
        tmp_path,
        edition=OTHER_EDITION,
        cache_dir=cache_dir,
        db_path=db_path,
    )

    result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "build-fixture", "--force"],
    )

    assert result.exit_code == 0, result.output
    assert db_path.is_file()
    # The profile's edition names a real KB; the fixture keeps its own label.
    assert (cache_dir / f"artifacts/{EDITION}/manifest.json").exists()
    assert not (cache_dir / f"artifacts/{OTHER_EDITION}").exists()


def test_build_fixture_ignores_an_exported_edition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DICOM_KB_EDITION", OTHER_EDITION)

    result = CliRunner().invoke(
        app,
        ["build-fixture", "--cache-dir", str(tmp_path), "--force"],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "db" / f"{EDITION}.sqlite").is_file()
    assert not (tmp_path / "db" / f"{OTHER_EDITION}.sqlite").exists()


def test_cli_config_supplies_query_defaults(tmp_path: Path) -> None:
    cache_dir = tmp_path / "profile-cache"
    db_path = tmp_path / "profile.sqlite"
    config_path = _config_file(
        tmp_path,
        edition=OTHER_EDITION,
        cache_dir=cache_dir,
        db_path=db_path,
    )
    build_result = CliRunner().invoke(
        app,
        [
            "--config",
            str(config_path),
            "build-fixture",
            "--edition",
            OTHER_EDITION,
            "--force",
        ],
    )
    assert build_result.exit_code == 0, build_result.output

    lookup_result = CliRunner().invoke(
        app,
        ["--config", str(config_path), "element", "Modality"],
    )

    assert lookup_result.exit_code == 0, lookup_result.output
    assert lookup_result.output.rstrip().endswith(f"({OTHER_EDITION})")
    assert "`Modality` · VR CS" in lookup_result.output


def test_cli_flags_override_config_defaults(tmp_path: Path) -> None:
    profile_cache = tmp_path / "profile-cache"
    profile_db = tmp_path / "profile.sqlite"
    cli_cache = tmp_path / "cli-cache"
    cli_db = tmp_path / "cli.sqlite"
    config_path = _config_file(
        tmp_path,
        edition=OTHER_EDITION,
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
            EDITION,
            "--cache-dir",
            str(cli_cache),
            "--db",
            str(cli_db),
            "--force",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output.startswith(f"Built DICOM {EDITION} KB: {cli_db}")
    assert (cli_cache / f"artifacts/{EDITION}/manifest.json").exists()
    assert not (profile_cache / f"artifacts/{OTHER_EDITION}/manifest.json").exists()


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
        """,
        encoding="utf-8",
    )
    return path

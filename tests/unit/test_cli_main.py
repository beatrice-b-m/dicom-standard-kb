from typer.testing import CliRunner

from dicom_kb.cli.main import app


def test_cli_version_exits_without_a_subcommand() -> None:
    result = CliRunner().invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.output == "dicom-standard-kb 0.1.0\n"

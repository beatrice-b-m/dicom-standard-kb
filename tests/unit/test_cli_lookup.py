from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from click.utils import strip_ansi
from typer.testing import CliRunner

from dicom_kb.cli.main import app
from dicom_kb.db.importers import (
    import_attribute_value_terms,
    import_coded_concepts,
    import_context_groups,
    import_dicom_media_types,
    import_dicomweb_transactions,
    import_docbook_structure,
    import_part03,
    import_part04,
    import_part06,
    import_sr_templates,
    import_transfer_syntax_details,
    import_vr_definitions,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part03_iods import parse_part03
from dicom_kb.parsers.part04_sop_classes import parse_part04
from dicom_kb.parsers.part05_encoding import (
    parse_part05,
    transfer_syntax_details_from_uid_registry,
)
from dicom_kb.parsers.part06_data_dictionary import parse_part06
from dicom_kb.parsers.part10_media_storage import parse_part10
from dicom_kb.parsers.part16_content_mapping import parse_part16
from dicom_kb.parsers.part18_web_services import parse_part18
from dicom_kb.sources.downloader import (
    DEFAULT_DOCBOOK_PARTS,
    official_docbook_xml_url,
)
from tests.fixtures_synthetic import (
    FIXTURE_DIR,
    PS33_CT_IMAGE_DOCBOOK,
    PS34_SOP_CLASSES_DOCBOOK,
    PS35_ENCODING_DOCBOOK,
    PS36_REGISTRY_DOCBOOK,
    PS310_MEDIA_STORAGE_DOCBOOK,
    PS316_CONTENT_MAPPING_DOCBOOK,
    PS318_WEB_SERVICES_DOCBOOK,
)

_RICH_BOX_CHARS = str.maketrans("", "", "\u256d\u2500\u256e\u2502\u2570\u256f")


class _FakeResponse(BytesIO):
    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.close()


def _fixture_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "kb.sqlite"
    connection = connect_sqlite(db_path)
    apply_migrations(connection)
    parsed = parse_part06(
        parse_docbook_xml(PS36_REGISTRY_DOCBOOK, part="PS3.6"),
        edition="2026b",
    )
    import_part06(
        connection,
        edition="2026b",
        data_elements=parsed.data_elements,
        uid_registry_entries=parsed.uid_registry_entries,
    )
    part05_document = parse_docbook_xml(PS35_ENCODING_DOCBOOK, part="PS3.5")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=part05_document,
    )
    parsed_part05 = parse_part05(part05_document, edition="2026b")
    import_vr_definitions(
        connection,
        edition="2026b",
        vr_definitions=parsed_part05.vr_definitions,
    )
    import_transfer_syntax_details(
        connection,
        edition="2026b",
        transfer_syntax_details=transfer_syntax_details_from_uid_registry(
            edition="2026b",
            uid_registry_entries=parsed.uid_registry_entries,
        ),
    )
    part03_document = parse_docbook_xml(PS33_CT_IMAGE_DOCBOOK, part="PS3.3")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=part03_document,
    )
    parsed_part03 = parse_part03(part03_document, edition="2026b")
    import_part03(
        connection,
        edition="2026b",
        iods=parsed_part03.iods,
        modules=parsed_part03.modules,
        macros=parsed_part03.macros,
        iod_module_uses=parsed_part03.iod_module_uses,
        iod_functional_group_uses=parsed_part03.iod_functional_group_uses,
        attribute_uses=parsed_part03.attribute_uses,
        conditions=parsed_part03.conditions,
    )
    import_attribute_value_terms(
        connection,
        edition="2026b",
        document=part03_document,
    )
    parsed_part04 = parse_part04(
        parse_docbook_xml(PS34_SOP_CLASSES_DOCBOOK, part="PS3.4"),
        edition="2026b",
    )
    import_part04(
        connection,
        edition="2026b",
        service_classes=parsed_part04.service_classes,
        sop_classes=parsed_part04.sop_classes,
        sop_class_iods=parsed_part04.sop_class_iods,
    )
    parsed_part10 = parse_part10(
        parse_docbook_xml(PS310_MEDIA_STORAGE_DOCBOOK, part="PS3.10"),
        edition="2026b",
    )
    import_dicom_media_types(
        connection,
        edition="2026b",
        media_types=parsed_part10.media_types,
    )
    parsed_part16 = parse_part16(
        parse_docbook_xml(PS316_CONTENT_MAPPING_DOCBOOK, part="PS3.16"),
        edition="2026b",
    )
    import_sr_templates(
        connection,
        edition="2026b",
        templates=parsed_part16.sr_templates,
        rows=parsed_part16.sr_template_rows,
    )
    import_context_groups(
        connection,
        edition="2026b",
        context_groups=parsed_part16.context_groups,
        rows=parsed_part16.context_group_rows,
    )
    import_coded_concepts(
        connection,
        edition="2026b",
        coded_concepts=parsed_part16.coded_concepts,
    )
    part18_document = parse_docbook_xml(PS318_WEB_SERVICES_DOCBOOK, part="PS3.18")
    import_docbook_structure(
        connection,
        edition="2026b",
        document=part18_document,
    )
    parsed_part18 = parse_part18(part18_document, edition="2026b")
    import_dicomweb_transactions(
        connection,
        edition="2026b",
        transactions=parsed_part18.dicomweb_transactions,
    )
    import_dicom_media_types(
        connection,
        edition="2026b",
        media_types=parsed_part18.media_types,
    )
    connection.close()
    return db_path


def _invoke(tmp_path: Path, *args: str) -> str:
    result = CliRunner().invoke(
        app, [*args, "--edition", "2026b", "--db", str(_fixture_db(tmp_path))]
    )
    assert result.exit_code == 0, result.output
    return result.output


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(
            ["lookup", "tag", "(0008,0060)"],
            [
                "**(0008,0060) Modality**\nKeyword `Modality` · VR CS · VM 1\n\n"
                "Source: PS3.6 Table 6-1 (2026b)\n"
            ],
            id="lookup tag",
        ),
        pytest.param(
            ["lookup", "tag", "0008,0060"],
            ["malformed DICOM tag"],
            id="validation error",
        ),
        pytest.param(
            ["lookup", "tag", "(6002,3000)"],
            [
                "**(60xx,3000) Overlay Data**",
                "Warning: concrete tag (6002,3000) matched range row (60xx,3000)",
            ],
            id="range match",
        ),
        pytest.param(
            ["lookup", "uid", "ExplicitVRBigEndian"],
            ["**1.2.840.10008.1.2.2** Explicit VR Big Endian (retired)"],
            id="uid",
        ),
        pytest.param(
            ["lookup", "vr", "pn"], ["**Name:** Person Name", "Source: PS3.5"], id="vr"
        ),
        pytest.param(
            ["lookup", "transfer-syntax", "ExplicitVRLittleEndian"],
            ["**Explicit vr:** yes", "**Endian:** little"],
            id="transfer syntax",
        ),
        pytest.param(
            ["lookup", "media-type", "file"],
            ["**Media type:** application/dicom", "Source: PS3.10"],
            id="media type",
        ),
        pytest.param(
            ["lookup", "media-type", "STOW-RS request"],
            ["**Media type:** multipart/related", "Source: PS3.18"],
            id="media type ps3.18",
        ),
        pytest.param(
            ["lookup", "dicomweb", "RetrieveStudy"],
            ["**Route template:** /studies/{studyInstanceUID}"],
            id="dicomweb",
        ),
        pytest.param(
            ["lookup", "sr-template", "TID 1500"],
            [
                "**TID 1500 Measurement Report**",
                "| CONTAINS | INCLUDE | Include TID 1501 | 1-n |",
            ],
            id="sr template",
        ),
        pytest.param(
            ["lookup", "context-group", "CID 29"],
            ["**CID 29 Acquisition Modality**", "| DCM | CT | Computed Tomography |"],
            id="context group",
        ),
        pytest.param(
            ["lookup", "code", "CT", "--scheme", "DCM"],
            ["**Code meaning:** Computed Tomography", "- CID 29"],
            id="code",
        ),
        pytest.param(
            ["explain", "encoding", "OB"],
            ["OB is the Other Byte VR.", "- binary or text: binary"],
            id="explain encoding",
        ),
        pytest.param(
            ["lookup", "defined-terms", "PatientName", "--context", "CT Image Storage"],
            ["| ALPHA | Alphabetic representation. | Defined |", "| IDEOGRAPHIC |"],
            id="defined terms",
        ),
        pytest.param(
            ["retrieve-text", "PS3.3", "sect_A.3", "--max-chars", "60"],
            [
                "**PS3.3 A.3 CT Image IOD**",
                "Warning: text excerpt truncated to 60 characters",
            ],
            id="retrieve text",
        ),
        pytest.param(
            ["search-text", "Patient name", "--part", "PS3.3", "--limit", "3"],
            ["| PS3.3 Table C.7-1 | Patient Module Attributes |"],
            id="search text",
        ),
        pytest.param(
            ["lookup", "iod", "CT Image"], ["**CT Image IOD** (Table A.3-1)"], id="iod"
        ),
        pytest.param(
            ["lookup", "sop-class", "CT Image Storage"],
            ["**CT Image Storage** 1.2.840.10008.5.1.4.1.1.2", "IOD: CT Image"],
            id="sop class",
        ),
        pytest.param(
            ["iod", "modules", "CT Image"],
            ["| Image | Contrast/Bolus | C: Required if contrast media was used |"],
            id="iod modules",
        ),
        pytest.param(
            ["module", "attributes", "Patient", "--expand-macros"],
            [
                "| >Referenced SOP Class UID | (0008,1150) | 1 |",
                "| Include General Anatomy Optional Macro |",
                "| Anatomic Region Sequence | (0008,2218) | 3 | Region. |",
            ],
            id="module attributes",
        ),
        pytest.param(
            ["resolve", "attribute-context", "PatientName", "--iod", "CT Image"],
            ["Effective Type: 2", "| CT Image | Patient | M | 2 |"],
            id="attribute context",
        ),
        pytest.param(
            ["context", "attribute", "PatientName", "--iod", "CT Image"],
            ["Effective Type: 2"],
            id="context alias",
        ),
    ],
)
def test_cli_query_commands_print_markdown(
    tmp_path: Path, args: list[str], expected: list[str]
) -> None:
    output = _invoke(tmp_path, *args)

    for fragment in expected:
        assert fragment in output
    assert not output.lstrip().startswith("{")


def test_cli_lookup_tag_requires_existing_db(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "lookup",
            "tag",
            "Modality",
            "--edition",
            "2026b",
            "--db",
            str(tmp_path / "missing.sqlite"),
        ],
    )

    assert result.exit_code != 0
    assert "SQLite KB does not exist" in result.output


def test_cli_build_fixture_creates_default_db_for_lookups(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    runner = CliRunner()

    build_result = runner.invoke(
        app,
        [
            "build-fixture",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert build_result.exit_code == 0, build_result.output
    db_path = cache_dir / "db" / "2026b.sqlite"
    assert build_result.output.startswith(f"Built DICOM 2026b KB: {db_path}")
    assert "gaps logged" in build_result.output
    assert (cache_dir / "db" / "2026b.gaps.txt").exists()

    lookup_result = runner.invoke(
        app,
        [
            "lookup",
            "tag",
            "Modality",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert lookup_result.exit_code == 0, lookup_result.output
    assert lookup_result.output.startswith("**(0008,0060) Modality**")


def test_cli_fetch_registers_local_docbook_for_build(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    runner = CliRunner()

    fetch_result = runner.invoke(
        app,
        [
            "fetch",
            "--edition",
            "2026b",
            "--cache-dir",
            str(cache_dir),
            "--docbook-xml",
            f"PS3.6={FIXTURE_DIR / 'synthetic_ps3_6_registry_docbook.xml'}",
        ],
    )

    assert fetch_result.exit_code == 0, fetch_result.output
    assert fetch_result.output.startswith("Fetched DICOM 2026b: 1 parts")
    assert (cache_dir / "artifacts/2026b/raw/source/docbook/part06/part06.xml").exists()

    build_result = runner.invoke(
        app,
        [
            "build",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert build_result.exit_code == 0, build_result.output

    lookup_result = runner.invoke(
        app,
        [
            "lookup",
            "tag",
            "Modality",
            "--cache-dir",
            str(cache_dir),
        ],
    )

    assert lookup_result.exit_code == 0, lookup_result.output
    assert "Keyword `Modality`" in lookup_result.output


def test_cli_fetch_downloads_official_docbook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    part_url = official_docbook_xml_url(base_url, "PS3.6")
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        part_url: b"<book><title>Part 6</title></book>",
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)
    cache_dir = tmp_path / "cache"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "fetch",
            "--cache-dir",
            str(cache_dir),
            "--source-base-url",
            base_url,
            "--part",
            "PS3.6",
        ],
    )

    assert result.exit_code == 0, result.output
    assert result.output.startswith("Fetched DICOM 2026b: 1 parts")
    assert "Next: dicom-kb build --edition 2026b" in result.output
    assert (
        cache_dir / "artifacts/2026b/raw/source/docbook/part06/part06.xml"
    ).read_bytes() == responses[part_url]

    again = runner.invoke(
        app,
        [
            "fetch",
            "--cache-dir",
            str(cache_dir),
            "--source-base-url",
            base_url,
            "--part",
            "PS3.6",
        ],
    )
    assert again.exit_code != 0
    output = " ".join(strip_ansi(again.output).translate(_RICH_BOX_CHARS).split())
    assert "already fetched" in output


def test_cli_fetch_defaults_to_v2_docbook_parts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base_url = "https://dicom.example/current/"
    responses = {
        base_url: (
            b'<a href="DocBookDICOM2026b_release_docbook_20260327091344.zip">'
            b"docbook</a>"
        ),
        **{
            official_docbook_xml_url(base_url, part): (
                f"<book><title>{part}</title></book>".encode()
            )
            for part in DEFAULT_DOCBOOK_PARTS
        },
    }

    def fake_urlopen(url: str, timeout: int) -> _FakeResponse:
        assert timeout == 60
        return _FakeResponse(responses[url])

    monkeypatch.setattr("dicom_kb.sources.downloader.urlopen", fake_urlopen)
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "fetch",
            "--cache-dir",
            str(tmp_path / "cache"),
            "--source-base-url",
            base_url,
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"{len(DEFAULT_DOCBOOK_PARTS)} parts" in result.output

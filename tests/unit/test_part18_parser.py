from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dicom_kb.db.importers import import_dicomweb_transactions, import_docbook_structure
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part18_web_services import parse_part18
from tests.fixtures_synthetic import PS318_WEB_SERVICES_DOCBOOK


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_parse_part18_classifies_transaction_tables_and_warns_on_gaps() -> None:
    document = parse_docbook_xml(PS318_WEB_SERVICES_DOCBOOK, part="PS3.18")

    result = parse_part18(document, edition="2026b")

    assert [table.table_id for table in result.recognized_tables] == ["table_18-1"]
    transaction_table = result.recognized_tables[0]
    assert transaction_table.table_kind == "dicomweb_transaction"
    assert transaction_table.source_ref.part == "PS3.18"
    assert transaction_table.source_ref.section == "sect_18_1"
    assert transaction_table.source_ref.table_id == "table_18-1"
    assert transaction_table.source_ref.title == "Synthetic Transactions"
    assert [
        (record.transaction_name, record.http_method, record.route_template)
        for record in result.dicomweb_transactions
    ] == [
        ("RetrieveStudy", "GET", "/studies/{studyInstanceUID}"),
        ("StoreInstances", "POST", "/studies/{studyInstanceUID}"),
    ]
    retrieve_study = result.dicomweb_transactions[0]
    assert retrieve_study.resource_category == "study"
    assert retrieve_study.request_constraints == ("Study Instance UID required",)
    assert retrieve_study.response_constraints == ("DICOM instances returned",)
    assert retrieve_study.status_codes == ("200", "400", "404")
    assert retrieve_study.media_type_refs == ("application/dicom",)
    assert retrieve_study.source_ref.table_id == "table_18-1"
    assert [(warning.table_id, warning.message) for warning in result.warnings] == [
        ("table_18-2", "unsupported PS3.18 table shape")
    ]


def test_import_dicomweb_transactions_persists_rows_with_source_refs(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS318_WEB_SERVICES_DOCBOOK, part="PS3.18")
    parsed = parse_part18(document, edition="2026b")

    summary = import_dicomweb_transactions(
        connection,
        edition="2026b",
        transactions=parsed.dicomweb_transactions,
    )

    assert summary.dicomweb_transactions == 2
    assert summary.source_refs == 1
    rows = connection.execute(
        """
        SELECT txn.transaction_name, txn.resource_category, txn.http_method,
               txn.route_template, txn.request_constraints_json,
               txn.response_constraints_json, txn.status_codes_json,
               txn.media_type_refs_json, ref.part, ref.table_id
        FROM dicomweb_transaction txn
        JOIN source_ref ref ON ref.id = txn.source_ref_id
        WHERE txn.edition_id = ?
        ORDER BY txn.transaction_name
        """,
        ("2026b",),
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "transaction_name": "RetrieveStudy",
            "resource_category": "study",
            "http_method": "GET",
            "route_template": "/studies/{studyInstanceUID}",
            "request_constraints_json": json.dumps(
                ("Study Instance UID required",),
                separators=(",", ":"),
            ),
            "response_constraints_json": json.dumps(
                ("DICOM instances returned",),
                separators=(",", ":"),
            ),
            "status_codes_json": json.dumps(
                ("200", "400", "404"),
                separators=(",", ":"),
            ),
            "media_type_refs_json": json.dumps(
                ("application/dicom",),
                separators=(",", ":"),
            ),
            "part": "PS3.18",
            "table_id": "table_18-1",
        },
        {
            "transaction_name": "StoreInstances",
            "resource_category": "study",
            "http_method": "POST",
            "route_template": "/studies/{studyInstanceUID}",
            "request_constraints_json": json.dumps(
                ("Multipart request body required",),
                separators=(",", ":"),
            ),
            "response_constraints_json": json.dumps(
                ("Store response returned",),
                separators=(",", ":"),
            ),
            "status_codes_json": json.dumps(
                ("200", "202", "409"),
                separators=(",", ":"),
            ),
            "media_type_refs_json": json.dumps(
                ("multipart/related", "application/dicom"),
                separators=(",", ":"),
            ),
            "part": "PS3.18",
            "table_id": "table_18-1",
        },
    ]


def test_part18_docbook_structure_persists_nodes_refs_and_raw_table_ir(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS318_WEB_SERVICES_DOCBOOK, part="PS3.18")

    summary = import_docbook_structure(
        connection,
        edition="2026b",
        document=document,
    )

    assert summary.doc_nodes == 5
    assert summary.raw_table_irs == 2
    section = connection.execute(
        """
        SELECT node.title, ref.part, ref.xml_id
        FROM doc_node node
        JOIN source_ref ref ON ref.id = node.source_ref_id
        WHERE node.xml_id = ?
        """,
        ("sect_18_1",),
    ).fetchone()
    assert dict(section) == {
        "title": "DICOMweb Overview",
        "part": "PS3.18",
        "xml_id": "sect_18_1",
    }

    raw_table = connection.execute(
        """
        SELECT ir.ir_json, ir.ir_sha256, ref.part, ref.table_id
        FROM raw_table_ir ir
        JOIN source_ref ref ON ref.id = ir.source_ref_id
        WHERE ir.table_id = ?
        """,
        ("table_18-1",),
    ).fetchone()
    payload = json.loads(raw_table["ir_json"])
    assert payload["title"] == "Synthetic Transactions"
    assert payload["rows"][1]["cells"][0]["text"] == "RetrieveStudy"
    assert len(raw_table["ir_sha256"]) == 64
    assert raw_table["part"] == "PS3.18"
    assert raw_table["table_id"] == "table_18-1"

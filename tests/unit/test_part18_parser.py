from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from dicom_kb.db.importers import (
    import_dicom_media_types,
    import_dicomweb_transactions,
    import_docbook_structure,
)
from dicom_kb.db.models import apply_migrations, connect_sqlite
from dicom_kb.docbook.parser import parse_docbook_xml
from dicom_kb.parsers.part18_web_services import parse_part18
from tests.fixtures_synthetic import (
    PS318_OFFICIAL_SHAPE_DOCBOOK,
    PS318_WEB_SERVICES_DOCBOOK,
)


def _connection(tmp_path: Path) -> sqlite3.Connection:
    connection = connect_sqlite(tmp_path / "kb.sqlite")
    apply_migrations(connection)
    return connection


def test_parse_part18_classifies_transaction_tables_and_warns_on_gaps() -> None:
    document = parse_docbook_xml(PS318_WEB_SERVICES_DOCBOOK, part="PS3.18")

    result = parse_part18(document, edition="2026b")

    assert [table.table_id for table in result.recognized_tables] == [
        "table_18-1",
        "table_18-2",
    ]
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
    media_type_table = result.recognized_tables[1]
    assert media_type_table.table_kind == "media_type"
    assert media_type_table.source_ref.table_id == "table_18-2"
    assert [
        (record.media_type, record.service_context, record.directions)
        for record in result.media_types
    ] == [
        ("application/dicom", "WADO-RS response", ("response",)),
        ("multipart/related", "STOW-RS request", ("request",)),
    ]
    stow_media_type = result.media_types[1]
    assert stow_media_type.transfer_syntax_constraints == (
        "Each part supplies a DICOM instance payload",
    )
    assert stow_media_type.source_ref.table_id == "table_18-2"
    assert [(warning.table_id, warning.message) for warning in result.warnings] == [
        ("table_18-3", "unsupported PS3.18 table shape")
    ]


def test_parse_part18_official_shape_derives_release_examples() -> None:
    document = parse_docbook_xml(PS318_OFFICIAL_SHAPE_DOCBOOK, part="PS3.18")

    result = parse_part18(document, edition="2026b")

    assert [
        (table.table_id, table.table_kind)
        for table in result.recognized_tables
    ] == [
        ("table_8.7.3-2", "media_type"),
        ("table_10.3-1", "dicomweb_transaction_overview"),
        ("table_10.4.1-1", "dicomweb_transaction_resource"),
        ("table_10.5.1-1", "dicomweb_transaction_resource"),
    ]
    assert result.warnings == ()
    assert [
        (record.media_type, record.service_context, record.directions)
        for record in result.media_types
    ] == [
        ("application/dicom", "Instance Media Types", ("response",)),
        ("multipart/related", "WADO-RS response", ("response",)),
        ("multipart/related", "STOW-RS request", ("request",)),
    ]
    media_type = result.media_types[0]
    assert media_type.source_ref.table_id == "table_8.7.3-2"
    assert media_type.transfer_syntax_constraints == (
        "1.2.840.10008.1.2.1 Explicit VR Little Endian (D)",
    )
    assert result.media_types[1].source_ref.table_id == "table_10.4.1-1"
    assert result.media_types[1].transfer_syntax_constraints == (
        "Retrieve response payload: Instance(s), Metadata, Renderings, "
        "Pixel Data, or Bulk Data",
    )
    assert result.media_types[2].source_ref.table_id == "table_10.5.1-1"
    assert result.media_types[2].transfer_syntax_constraints == (
        "Store request payload: DICOM Instances",
    )
    assert [
        (
            record.transaction_name,
            record.resource_category,
            record.http_method,
            record.route_template,
        )
        for record in result.dicomweb_transactions
    ] == [
        ("RetrieveStudy", "study", "GET", "/studies/{study}"),
        ("RetrieveSeries", "series", "GET", "/studies/{study}/series/{series}"),
        ("StoreInstances", "study", "POST", "/studies/{study}"),
    ]
    retrieve_study = result.dicomweb_transactions[0]
    assert retrieve_study.request_constraints == ("Target resource: Study Instances",)
    assert retrieve_study.response_constraints == (
        "Success response payload: Instance(s), Metadata, Renderings, "
        "Pixel Data, or Bulk Data",
        "Retrieve one or more representations of DICOM Resources.",
    )
    assert all(
        "Store Instances" not in constraint
        for constraint in retrieve_study.response_constraints
    )
    assert retrieve_study.media_type_refs == (
        "application/dicom",
        "application/dicom+json",
    )
    assert retrieve_study.source_ref.table_id == "table_10.4.1-1"
    store_instances = result.dicomweb_transactions[2]
    assert store_instances.request_constraints == (
        "Target resource: Study Instances",
        "Request payload: DICOM Instances",
    )
    assert store_instances.response_constraints == (
        "Success response payload: Store Instances Response Module",
        "Store one or more DICOM Instances.",
    )
    assert store_instances.media_type_refs == (
        "multipart/related",
        "application/dicom",
    )
    assert store_instances.source_ref.table_id == "table_10.5.1-1"


def test_parse_part18_deduplicates_derived_official_media_contexts() -> None:
    duplicate_retrieve_table = """
    <section xml:id="sect_10.4.2.1.1">
      <title>Additional Retrieve Resources</title>
      <table xml:id="table_10.4.2-1">
        <caption>Retrieve Transaction Resources</caption>
        <thead>
          <tr>
            <th>Resource</th>
            <th>URI Template</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Instance Bulk Data</td>
            <td>/studies/{study}/series/{series}/instances/{instance}/bulkdata</td>
          </tr>
        </tbody>
      </table>
    </section>
"""
    document = parse_docbook_xml(
        PS318_OFFICIAL_SHAPE_DOCBOOK.replace(
            "    <section xml:id=\"sect_10.5.1.1.1\">",
            f"{duplicate_retrieve_table}    <section xml:id=\"sect_10.5.1.1.1\">",
        ),
        part="PS3.18",
    )

    result = parse_part18(document, edition="2026b")

    contexts = [
        (record.media_type, record.service_context) for record in result.media_types
    ]
    assert contexts.count(("multipart/related", "WADO-RS response")) == 1
    assert any(
        record.transaction_name == "RetrieveInstanceBulkData"
        for record in result.dicomweb_transactions
    )


def test_parse_part18_uses_same_family_overview_for_retrieve_resources() -> None:
    later_retrieve_overview = """
    <section xml:id="sect_11.3">
      <title>Unrelated Retrieve Overview</title>
      <table xml:id="table_11.3-1">
        <caption>Unrelated Service Transactions</caption>
        <thead>
          <tr>
            <th rowspan="2">Transaction Name</th>
            <th rowspan="2">Method</th>
            <th colspan="2">Payload</th>
            <th rowspan="2">Description</th>
          </tr>
          <tr>
            <th>Request</th>
            <th>Success Response</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>Retrieve</td>
            <td>GET</td>
            <td>N/A</td>
            <td>Data Set according to</td>
            <td>Retrieves the target Modality Performed Procedure Step</td>
          </tr>
        </tbody>
      </table>
    </section>
"""
    document = parse_docbook_xml(
        PS318_OFFICIAL_SHAPE_DOCBOOK.replace(
            "  </chapter>",
            f"{later_retrieve_overview}  </chapter>",
        ),
        part="PS3.18",
    )

    result = parse_part18(document, edition="2026b")

    retrieve_study = next(
        record
        for record in result.dicomweb_transactions
        if record.transaction_name == "RetrieveStudy"
    )
    assert retrieve_study.response_constraints == (
        "Success response payload: Instance(s), Metadata, Renderings, "
        "Pixel Data, or Bulk Data",
        "Retrieve one or more representations of DICOM Resources.",
    )


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


def test_import_dicom_media_types_persists_ps318_contexts_with_source_refs(
    tmp_path: Path,
) -> None:
    connection = _connection(tmp_path)
    document = parse_docbook_xml(PS318_WEB_SERVICES_DOCBOOK, part="PS3.18")
    parsed = parse_part18(document, edition="2026b")

    summary = import_dicom_media_types(
        connection,
        edition="2026b",
        media_types=parsed.media_types,
    )

    assert summary.dicom_media_types == 2
    assert summary.source_refs == 1
    rows = connection.execute(
        """
        SELECT media.media_type, media.service_context,
               media.transfer_syntax_constraints_json, media.directions_json,
               ref.part, ref.table_id
        FROM dicom_media_type media
        JOIN source_ref ref ON ref.id = media.source_ref_id
        WHERE media.edition_id = ?
        ORDER BY media.service_context
        """,
        ("2026b",),
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "media_type": "multipart/related",
            "service_context": "STOW-RS request",
            "transfer_syntax_constraints_json": json.dumps(
                ("Each part supplies a DICOM instance payload",),
                separators=(",", ":"),
            ),
            "directions_json": json.dumps(("request",), separators=(",", ":")),
            "part": "PS3.18",
            "table_id": "table_18-2",
        },
        {
            "media_type": "application/dicom",
            "service_context": "WADO-RS response",
            "transfer_syntax_constraints_json": json.dumps(
                ("Rendered transfer syntax negotiated by Accept header",),
                separators=(",", ":"),
            ),
            "directions_json": json.dumps(("response",), separators=(",", ":")),
            "part": "PS3.18",
            "table_id": "table_18-2",
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

    assert summary.doc_nodes == 6
    assert summary.raw_table_irs == 3
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

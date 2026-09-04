"""DocBook structure and full-text index import."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict

from dicom_kb.db.importers._shared import (
    ImportSummary,
    _insert_source_ref,
    _unique_source_refs,
)
from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.ir.models import (
    DocNode,
    RawTableIR,
    SourceRef,
    Xref,
)


def import_docbook_structure(
    connection: sqlite3.Connection,
    *,
    edition: str,
    document: ParsedDocument,
) -> ImportSummary:
    """Import parsed DocBook structure, xrefs, and raw table snapshots."""
    nodes = _doc_nodes_from_document(edition, document)
    node_by_xml_id = {node.xml_id: node for node in nodes if node.xml_id is not None}
    raw_tables = _raw_table_irs_from_document(edition, document)
    xrefs = _xrefs_from_document(edition, document, node_by_xml_id)
    source_refs = _unique_source_refs(
        [node.source_ref for node in nodes] + [table.source_ref for table in raw_tables]
    )

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for node in nodes:
                _insert_doc_node(connection, node)
            for table in raw_tables:
                _insert_raw_table_ir(connection, table)
            for xref in xrefs:
                _insert_xref(connection, xref)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import DocBook structure for {edition} {document.part}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        doc_nodes=len(nodes),
        xrefs=len(xrefs),
        xrefs_unresolved=sum(1 for xref in xrefs if not xref.resolved),
        raw_table_irs=len(raw_tables),
    )


def _doc_nodes_from_document(
    edition: str, document: ParsedDocument
) -> tuple[DocNode, ...]:
    root_source_ref = SourceRef(
        id=f"{edition}.{document.part}.book",
        edition_id=edition,
        part=document.part,
        title=document.part,
    )
    root = DocNode(
        id=f"{edition}.{document.part}.book",
        edition_id=edition,
        part=document.part,
        node_type="book",
        ordinal=0,
        title=document.part,
        source_ref=root_source_ref,
    )

    nodes: list[DocNode] = [root]
    section_by_xml_id: dict[str, str] = {}
    for section in document.sections:
        source_ref = SourceRef(
            id=_doc_source_ref_id(
                edition, document.part, "section", section.xml_id, section.ordinal
            ),
            edition_id=edition,
            part=document.part,
            section=section.number or section.xml_id,
            xml_id=section.xml_id,
            title=section.title,
        )
        node = DocNode(
            id=_doc_node_id(
                edition, document.part, section.xml_id, "section", section.ordinal
            ),
            edition_id=edition,
            part=document.part,
            node_type=section.node_type,
            parent_id=(
                section_by_xml_id.get(section.parent_xml_id, root.id)
                if section.parent_xml_id is not None
                else root.id
            ),
            xml_id=section.xml_id,
            anchor=section.xml_id,
            number=section.number,
            title=section.title,
            ordinal=section.ordinal,
            plain_text=section.plain_text,
            source_ref=source_ref,
        )
        nodes.append(node)
        if section.xml_id is not None:
            section_by_xml_id[section.xml_id] = node.id

    for table in document.tables:
        source_ref = SourceRef(
            id=_doc_source_ref_id(
                edition, document.part, "table", table.xml_id, table.ordinal
            ),
            edition_id=edition,
            part=document.part,
            section=table.parent_xml_id,
            table_id=table.xml_id,
            xml_id=table.xml_id,
            title=table.title,
        )
        row_text = " ".join(
            " ".join(cell.text for cell in row.cells) for row in table.rows
        )
        nodes.append(
            DocNode(
                id=_doc_node_id(
                    edition, document.part, table.xml_id, "table", table.ordinal
                ),
                edition_id=edition,
                part=document.part,
                node_type="table",
                parent_id=(
                    section_by_xml_id.get(table.parent_xml_id, root.id)
                    if table.parent_xml_id is not None
                    else root.id
                ),
                xml_id=table.xml_id,
                anchor=table.xml_id,
                title=table.title,
                ordinal=table.ordinal,
                plain_text=row_text,
                source_ref=source_ref,
            )
        )

    return tuple(nodes)


def _insert_doc_node(connection: sqlite3.Connection, node: DocNode) -> None:
    connection.execute(
        """
        INSERT INTO doc_node (
          id, edition_id, part, node_type, parent_id, xml_id, anchor, number,
          title, ordinal, plain_text, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            node.id,
            node.edition_id,
            node.part,
            node.node_type,
            node.parent_id,
            node.xml_id,
            node.anchor,
            node.number,
            node.title,
            node.ordinal,
            node.plain_text,
            node.source_ref.id,
        ),
    )
    connection.execute(
        """
        INSERT INTO doc_node_fts (
          node_id, edition_id, part, title, plain_text
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            node.id,
            node.edition_id,
            node.part,
            node.title,
            node.plain_text,
        ),
    )


def _insert_raw_table_ir(connection: sqlite3.Connection, table: RawTableIR) -> None:
    connection.execute(
        """
        INSERT INTO raw_table_ir (
          id, edition_id, part, table_id, title, ordinal, source_ref_id,
          ir_json, ir_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            table.id,
            table.edition_id,
            table.part,
            table.table_id,
            table.title,
            table.ordinal,
            table.source_ref.id,
            table.ir_json,
            table.ir_sha256,
        ),
    )


def _insert_xref(connection: sqlite3.Connection, xref: Xref) -> None:
    connection.execute(
        """
        INSERT INTO xref (
          id, edition_id, source_node_id, target_ref, target_node_id, link_type,
          resolved, resolution_warning, text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            xref.id,
            xref.edition_id,
            xref.source_node_id,
            xref.target_ref,
            xref.target_node_id,
            xref.link_type,
            int(xref.resolved),
            xref.resolution_warning,
            xref.text,
        ),
    )


def _raw_table_irs_from_document(
    edition: str, document: ParsedDocument
) -> tuple[RawTableIR, ...]:
    records: list[RawTableIR] = []
    for table in document.tables:
        payload = json.dumps(asdict(table), sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        source_ref = SourceRef(
            id=_doc_source_ref_id(
                edition, document.part, "table", table.xml_id, table.ordinal
            ),
            edition_id=edition,
            part=document.part,
            section=table.parent_xml_id,
            table_id=table.xml_id,
            xml_id=table.xml_id,
            title=table.title,
        )
        records.append(
            RawTableIR(
                id=_raw_table_ir_id(
                    edition, document.part, table.xml_id, table.ordinal
                ),
                edition_id=edition,
                part=document.part,
                table_id=table.xml_id,
                title=table.title,
                ordinal=table.ordinal,
                source_ref=source_ref,
                ir_json=payload,
                ir_sha256=digest,
            )
        )
    return tuple(records)


def _xrefs_from_document(
    edition: str,
    document: ParsedDocument,
    node_by_xml_id: dict[str, DocNode],
) -> tuple[Xref, ...]:
    root_id = f"{edition}.{document.part}.book"
    records: list[Xref] = []
    for ordinal, parsed in enumerate(document.xrefs):
        source_node = (
            node_by_xml_id.get(parsed.source_xml_id)
            if parsed.source_xml_id is not None
            else None
        )
        target_node = node_by_xml_id.get(parsed.target_ref)
        records.append(
            Xref(
                id=f"{edition}.{document.part}.xref.{ordinal}",
                edition_id=edition,
                source_node_id=source_node.id if source_node is not None else root_id,
                target_ref=parsed.target_ref,
                target_node_id=target_node.id if target_node is not None else None,
                link_type=parsed.link_type,
                resolved=parsed.resolved
                and (parsed.link_type == "olink" or target_node is not None),
                resolution_warning=parsed.warning,
                text=parsed.text,
            )
        )
    return tuple(records)


def _doc_node_id(
    edition: str, part: str, xml_id: str | None, node_type: str, ordinal: int
) -> str:
    return f"{edition}.{part}.{xml_id or f'{node_type}.{ordinal}'}"


def _doc_source_ref_id(
    edition: str, part: str, node_type: str, xml_id: str | None, ordinal: int
) -> str:
    return f"{edition}.{part}.{xml_id or f'{node_type}.{ordinal}'}"


def _raw_table_ir_id(edition: str, part: str, xml_id: str | None, ordinal: int) -> str:
    return f"{edition}.{part}.raw_table_ir.{xml_id or ordinal}"

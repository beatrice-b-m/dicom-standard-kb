"""Transactional import of parsed IR records into SQLite."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import cast

from dicom_kb.docbook.parser import ParsedDocument
from dicom_kb.docbook.text_chunks import normalize_text
from dicom_kb.docbook.variablelists import ParsedVariableList
from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    AttributeValueTerm,
    Condition,
    DataElement,
    DocNode,
    IODFunctionalGroupUse,
    IODModuleUse,
    Macro,
    Module,
    RawTableIR,
    ServiceClass,
    SOPClass,
    SOPClassIOD,
    SourceRef,
    UIDRegistryEntry,
    VRDefinition,
    Xref,
)
from dicom_kb.sources.manifest import SourceManifest
from dicom_kb.sources.official_urls import official_standard_ref_url


@dataclass(frozen=True)
class ImportSummary:
    """Counts emitted after an import transaction."""

    edition: str
    source_refs: int
    data_elements: int = 0
    uid_registry_entries: int = 0
    iods: int = 0
    modules: int = 0
    macros: int = 0
    iod_module_uses: int = 0
    iod_functional_group_uses: int = 0
    attribute_uses: int = 0
    conditions: int = 0
    service_classes: int = 0
    sop_classes: int = 0
    sop_class_iods: int = 0
    doc_nodes: int = 0
    xrefs: int = 0
    xrefs_unresolved: int = 0
    raw_table_irs: int = 0
    attribute_value_terms: int = 0
    vr_definitions: int = 0
    include_rows_resolved: int = 0
    include_rows_unresolved: int = 0


def import_manifest(connection: sqlite3.Connection, manifest: SourceManifest) -> None:
    """Import edition and artifact metadata from a source manifest."""
    with connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO standard_edition (
              id, source_label, resolved_from, acquired_at, is_default, manifest_sha256
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                manifest.edition,
                f"DICOM PS3 {manifest.edition}",
                manifest.resolved_from,
                manifest.acquired_at.isoformat(),
                0,
                manifest.source_manifest_sha256,
            ),
        )
        for artifact in manifest.artifacts:
            artifact_id = (
                f"{manifest.edition}.{artifact.part}.{artifact.format}."
                f"{artifact.sha256[:12]}"
            )
            connection.execute(
                """
                INSERT OR REPLACE INTO source_artifact (
                  id, edition_id, part, format, local_path, source_url, sha256,
                  byte_size, acquired_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact_id,
                    manifest.edition,
                    artifact.part,
                    artifact.format,
                    artifact.local_path,
                    artifact.source_url,
                    artifact.sha256,
                    artifact.byte_size,
                    manifest.acquired_at.isoformat(),
                ),
            )


def import_build_metadata(
    connection: sqlite3.Connection,
    *,
    edition: str,
    built_at: datetime,
    parser_version: str,
    schema_version: str,
    source_manifest_sha256: str,
    source_urls: Iterable[str],
    source_sha256: dict[str, str],
    repository_commit: str | None = None,
    metrics: dict[str, object] | None = None,
) -> None:
    """Record reproducible build metadata for a generated SQLite database."""
    metadata: dict[str, object] = {
        "edition": edition,
        "source_urls": tuple(source_urls),
        "source_sha256": source_sha256,
        "built_at": built_at.isoformat(),
        "parser_version": parser_version,
        "schema_version": schema_version,
        "repository_commit": repository_commit,
    }
    if metrics is not None:
        metadata["metrics"] = metrics
    with connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO build_metadata (
              edition_id, built_at, parser_version, schema_version,
              source_manifest_sha256, repository_commit, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                edition,
                built_at.isoformat(),
                parser_version,
                schema_version,
                source_manifest_sha256,
                repository_commit,
                json.dumps(metadata, sort_keys=True, separators=(",", ":")),
            ),
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


def import_part06(
    connection: sqlite3.Connection,
    *,
    edition: str,
    data_elements: Iterable[DataElement],
    uid_registry_entries: Iterable[UIDRegistryEntry],
) -> ImportSummary:
    """Import parsed PS3.6 records transactionally."""
    elements = tuple(data_elements)
    uids = tuple(uid_registry_entries)
    source_refs = _unique_source_refs(
        [record.source_ref for record in elements]
        + [record.source_ref for record in uids]
    )

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for element in elements:
                _insert_data_element(connection, element)
            for uid in uids:
                _insert_uid(connection, uid)
    except sqlite3.IntegrityError as exc:
        raise ImportError(f"failed to import PS3.6 records for {edition}") from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        data_elements=len(elements),
        uid_registry_entries=len(uids),
    )


def import_part03(
    connection: sqlite3.Connection,
    *,
    edition: str,
    iods: Iterable[IOD],
    modules: Iterable[Module],
    macros: Iterable[Macro],
    iod_module_uses: Iterable[IODModuleUse],
    iod_functional_group_uses: Iterable[IODFunctionalGroupUse],
    attribute_uses: Iterable[AttributeUse],
    conditions: Iterable[Condition] = (),
) -> ImportSummary:
    """Import parsed PS3.3 graph records transactionally."""
    iod_records = tuple(iods)
    module_records = tuple(modules)
    macro_records = tuple(macros)
    module_use_records = tuple(iod_module_uses)
    functional_group_use_records = tuple(iod_functional_group_uses)
    attribute_use_records = tuple(attribute_uses)
    condition_records = tuple(conditions)
    include_records = tuple(
        record for record in attribute_use_records if record.row_kind == "include"
    )
    source_refs = _unique_source_refs(
        [record.source_ref for record in iod_records]
        + [record.source_ref for record in module_records]
        + [record.source_ref for record in macro_records]
        + [record.source_ref for record in condition_records]
        + [record.source_ref for record in module_use_records]
        + [record.source_ref for record in functional_group_use_records]
        + [record.source_ref for record in attribute_use_records]
    )

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for iod in iod_records:
                _insert_iod(connection, iod)
            for module in module_records:
                _insert_module(connection, module)
            for macro in macro_records:
                _insert_macro(connection, macro)
            for condition in condition_records:
                _insert_condition(connection, condition)
            for module_use in module_use_records:
                _insert_iod_module_use(connection, module_use)
            for functional_group_use in functional_group_use_records:
                _insert_iod_functional_group_use(connection, functional_group_use)
            for attribute_use in attribute_use_records:
                _insert_attribute_use(connection, attribute_use)
    except sqlite3.IntegrityError as exc:
        raise ImportError(f"failed to import PS3.3 records for {edition}") from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        iods=len(iod_records),
        modules=len(module_records),
        macros=len(macro_records),
        iod_module_uses=len(module_use_records),
        iod_functional_group_uses=len(functional_group_use_records),
        attribute_uses=len(attribute_use_records),
        conditions=len(condition_records),
        include_rows_resolved=sum(
            1 for record in include_records if record.included_macro_id is not None
        ),
        include_rows_unresolved=sum(
            1
            for record in include_records
            if record.include_target_text is not None
            and record.included_macro_id is None
        ),
    )


def import_part04(
    connection: sqlite3.Connection,
    *,
    edition: str,
    service_classes: Iterable[ServiceClass],
    sop_classes: Iterable[SOPClass],
    sop_class_iods: Iterable[SOPClassIOD],
) -> ImportSummary:
    """Import parsed PS3.4 SOP Class records transactionally."""
    service_class_records = tuple(service_classes)
    sop_class_records = tuple(sop_classes)
    sop_class_iod_records = tuple(sop_class_iods)
    source_refs = _unique_source_refs(
        [record.source_ref for record in service_class_records]
        + [record.source_ref for record in sop_class_records]
        + [record.source_ref for record in sop_class_iod_records]
    )

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for service_class in service_class_records:
                _insert_service_class(connection, service_class)
            for sop_class in sop_class_records:
                _insert_sop_class(connection, sop_class)
            for sop_class_iod in sop_class_iod_records:
                _insert_sop_class_iod(connection, sop_class_iod)
    except sqlite3.IntegrityError as exc:
        raise ImportError(f"failed to import PS3.4 records for {edition}") from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        service_classes=len(service_class_records),
        sop_classes=len(sop_class_records),
        sop_class_iods=len(sop_class_iod_records),
    )


def import_attribute_value_terms(
    connection: sqlite3.Connection,
    *,
    edition: str,
    document: ParsedDocument,
) -> ImportSummary:
    """Import parsed enumerated values and defined terms from DocBook lists."""
    term_records = _attribute_value_terms_from_document(connection, edition, document)
    source_refs = _unique_source_refs(record.source_ref for record in term_records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for term in term_records:
                _insert_attribute_value_term(connection, term)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import attribute value terms for {edition} {document.part}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        attribute_value_terms=len(term_records),
    )


def import_vr_definitions(
    connection: sqlite3.Connection,
    *,
    edition: str,
    vr_definitions: Iterable[VRDefinition],
) -> ImportSummary:
    """Import parsed PS3.5 value representation definitions."""
    records = tuple(vr_definitions)
    source_refs = _unique_source_refs(record.source_ref for record in records)

    try:
        with connection:
            for source_ref in source_refs:
                _insert_source_ref(connection, source_ref)
            for record in records:
                _insert_vr_definition(connection, record)
    except sqlite3.IntegrityError as exc:
        raise ImportError(
            f"failed to import PS3.5 VR definitions for {edition}"
        ) from exc

    return ImportSummary(
        edition=edition,
        source_refs=len(source_refs),
        vr_definitions=len(records),
    )


def _unique_source_refs(source_refs: Iterable[SourceRef]) -> tuple[SourceRef, ...]:
    unique: dict[str, SourceRef] = {}
    for source_ref in source_refs:
        unique[source_ref.id] = source_ref
    return tuple(unique.values())


def _insert_source_ref(connection: sqlite3.Connection, source_ref: SourceRef) -> None:
    canonical_url = source_ref.canonical_url or official_standard_ref_url(
        edition=source_ref.edition_id,
        part=source_ref.part,
        anchor=source_ref.xml_id or source_ref.table_id,
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO source_ref (
          id, edition_id, part, section, table_id, xml_id, title, canonical_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_ref.id,
            source_ref.edition_id,
            source_ref.part,
            source_ref.section,
            source_ref.table_id,
            source_ref.xml_id,
            source_ref.title,
            canonical_url,
        ),
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


def _doc_source_ref_id(
    edition: str, part: str, node_type: str, xml_id: str | None, ordinal: int
) -> str:
    return f"{edition}.{part}.{xml_id or f'{node_type}.{ordinal}'}"


def _doc_node_id(
    edition: str, part: str, xml_id: str | None, node_type: str, ordinal: int
) -> str:
    return f"{edition}.{part}.{xml_id or f'{node_type}.{ordinal}'}"


def _raw_table_ir_id(edition: str, part: str, xml_id: str | None, ordinal: int) -> str:
    return f"{edition}.{part}.raw_table_ir.{xml_id or ordinal}"


def _insert_data_element(connection: sqlite3.Connection, element: DataElement) -> None:
    connection.execute(
        """
        INSERT INTO data_element (
          id, edition_id, tag, group_pattern, element_pattern, is_range, name,
          keyword, vr, vm, retired, retired_in_or_last_seen, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            element.id,
            element.edition_id,
            element.tag,
            element.group_pattern,
            element.element_pattern,
            int(element.is_range),
            element.name,
            element.keyword,
            element.vr,
            element.vm,
            int(element.retired),
            element.retired_in_or_last_seen,
            element.source_ref.id,
        ),
    )


def _insert_uid(connection: sqlite3.Connection, uid: UIDRegistryEntry) -> None:
    connection.execute(
        """
        INSERT INTO uid_registry_entry (
          id, edition_id, uid_value, uid_name, uid_keyword, uid_type, part,
          retired, retired_in_or_last_seen, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uid.id,
            uid.edition_id,
            uid.uid_value,
            uid.uid_name,
            uid.uid_keyword,
            uid.uid_type,
            uid.part,
            int(uid.retired),
            uid.retired_in_or_last_seen,
            uid.source_ref.id,
        ),
    )


def _insert_iod(connection: sqlite3.Connection, iod: IOD) -> None:
    connection.execute(
        """
        INSERT INTO iod (
          id, edition_id, name, keyword, iod_type, part, section, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            iod.id,
            iod.edition_id,
            iod.name,
            iod.keyword,
            iod.iod_type,
            iod.part,
            iod.section,
            iod.source_ref.id,
        ),
    )


def _insert_module(connection: sqlite3.Connection, module: Module) -> None:
    connection.execute(
        """
        INSERT INTO module (
          id, edition_id, name, section, description, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            module.id,
            module.edition_id,
            module.name,
            module.section,
            module.description,
            module.source_ref.id,
        ),
    )


def _insert_macro(connection: sqlite3.Connection, macro: Macro) -> None:
    connection.execute(
        """
        INSERT INTO macro (
          id, edition_id, name, table_id, section, macro_kind, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            macro.id,
            macro.edition_id,
            macro.name,
            macro.table_id,
            macro.section,
            macro.macro_kind,
            macro.source_ref.id,
        ),
    )


def _insert_condition(connection: sqlite3.Connection, condition: Condition) -> None:
    connection.execute(
        """
        INSERT INTO condition (
          id, edition_id, condition_kind, raw_text, normalized_text,
          machine_status, expression_json, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            condition.id,
            condition.edition_id,
            condition.condition_kind,
            condition.raw_text,
            condition.normalized_text,
            condition.machine_status,
            condition.expression_json,
            condition.source_ref.id,
        ),
    )


def _insert_iod_module_use(
    connection: sqlite3.Connection, module_use: IODModuleUse
) -> None:
    connection.execute(
        """
        INSERT INTO iod_module_use (
          id, edition_id, iod_id, information_entity, module_id, usage,
          usage_condition_text, condition_id, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            module_use.id,
            module_use.edition_id,
            module_use.iod_id,
            module_use.information_entity,
            module_use.module_id,
            module_use.usage,
            module_use.usage_condition_text,
            module_use.condition_id,
            module_use.source_ref.id,
        ),
    )


def _insert_iod_functional_group_use(
    connection: sqlite3.Connection, functional_group_use: IODFunctionalGroupUse
) -> None:
    connection.execute(
        """
        INSERT INTO iod_functional_group_use (
          id, edition_id, iod_id, macro_id, usage, usage_condition_text,
          condition_id, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            functional_group_use.id,
            functional_group_use.edition_id,
            functional_group_use.iod_id,
            functional_group_use.macro_id,
            functional_group_use.usage,
            functional_group_use.usage_condition_text,
            functional_group_use.condition_id,
            functional_group_use.source_ref.id,
        ),
    )


def _insert_attribute_use(
    connection: sqlite3.Connection, attribute_use: AttributeUse
) -> None:
    connection.execute(
        """
        INSERT INTO attribute_use (
          id, edition_id, owner_type, owner_id, parent_attribute_use_id, row_kind,
          attribute_tag, attribute_keyword, attribute_name, type_designation,
          description_text, condition_id, included_macro_id, include_target_text,
          sequence_depth, row_order, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            attribute_use.id,
            attribute_use.edition_id,
            attribute_use.owner_type,
            attribute_use.owner_id,
            attribute_use.parent_attribute_use_id,
            attribute_use.row_kind,
            attribute_use.attribute_tag,
            attribute_use.attribute_keyword,
            attribute_use.attribute_name,
            attribute_use.type_designation,
            attribute_use.description_text,
            attribute_use.condition_id,
            attribute_use.included_macro_id,
            attribute_use.include_target_text,
            attribute_use.sequence_depth,
            attribute_use.row_order,
            attribute_use.source_ref.id,
        ),
    )


def _insert_attribute_value_term(
    connection: sqlite3.Connection, term: AttributeValueTerm
) -> None:
    connection.execute(
        """
        INSERT INTO attribute_value_term (
          id, edition_id, attribute_use_id, data_element_id, context_label,
          term_kind, value, meaning, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            term.id,
            term.edition_id,
            term.attribute_use_id,
            term.data_element_id,
            term.context_label,
            term.term_kind,
            term.value,
            term.meaning,
            term.source_ref.id,
        ),
    )


def _insert_vr_definition(
    connection: sqlite3.Connection, record: VRDefinition
) -> None:
    connection.execute(
        """
        INSERT INTO vr_definition (
          id, edition_id, vr, name, value_representation_class,
          length_notes_json, padding_behavior, character_repertoire_notes_json,
          binary_or_text, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.edition_id,
            record.vr,
            record.name,
            record.value_representation_class,
            json.dumps(record.length_notes, sort_keys=True, separators=(",", ":")),
            record.padding_behavior,
            json.dumps(
                record.character_repertoire_notes,
                sort_keys=True,
                separators=(",", ":"),
            ),
            record.binary_or_text,
            record.source_ref.id,
        ),
    )


def _attribute_value_terms_from_document(
    connection: sqlite3.Connection, edition: str, document: ParsedDocument
) -> tuple[AttributeValueTerm, ...]:
    section_by_xml_id = {
        section.xml_id: section
        for section in document.sections
        if section.xml_id is not None
    }
    records: list[AttributeValueTerm] = []
    for variablelist in document.variablelists:
        term_kind = _value_term_kind(variablelist)
        if term_kind is None:
            continue
        section = (
            section_by_xml_id.get(variablelist.parent_xml_id)
            if variablelist.parent_xml_id is not None
            else None
        )
        data_element = _data_element_for_variablelist(
            connection,
            edition=edition,
            variablelist=variablelist,
            section_title=section.title if section is not None else None,
            section_text=section.plain_text if section is not None else None,
        )
        attribute_use_ids = (
            _attribute_use_ids_for_term_context(
                connection,
                edition=edition,
                data_element_id=str(data_element["id"]),
                data_element_tag=str(data_element["tag"]),
                parent_xml_id=variablelist.parent_xml_id,
            )
            if data_element is not None
            else ()
        )
        source_ref = SourceRef(
            id=_value_term_source_ref_id(edition, document.part, variablelist),
            edition_id=edition,
            part=document.part,
            section=variablelist.parent_xml_id,
            xml_id=variablelist.xml_id,
            title=variablelist.title,
        )
        for entry in variablelist.entries:
            for term_index, value in enumerate(entry.terms):
                targets = attribute_use_ids or (None,)
                for context_index, attribute_use_id in enumerate(targets):
                    records.append(
                        AttributeValueTerm(
                            id=_value_term_id(
                                edition,
                                document.part,
                                variablelist,
                                entry.entry_index,
                                term_index,
                                context_index,
                            ),
                            edition_id=edition,
                            attribute_use_id=attribute_use_id,
                            data_element_id=(
                                str(data_element["id"])
                                if data_element is not None
                                else None
                            ),
                            context_label=_value_term_context_label(
                                variablelist,
                                section_title=(
                                    section.title if section is not None else None
                                ),
                            ),
                            term_kind=term_kind,
                            value=value,
                            meaning=entry.definition or None,
                            source_ref=source_ref,
                        )
                    )
    return tuple(records)


def _value_term_kind(variablelist: ParsedVariableList) -> str | None:
    title = normalize_text(variablelist.title or "").lower().rstrip(":")
    if "enumerated value" in title:
        return "enumerated_value"
    if "defined term" in title:
        return "defined_term"
    return None


def _data_element_for_variablelist(
    connection: sqlite3.Connection,
    *,
    edition: str,
    variablelist: ParsedVariableList,
    section_title: str | None,
    section_text: str | None,
) -> sqlite3.Row | None:
    candidates = [
        section_title,
        variablelist.parent_xml_id,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        row = connection.execute(
            """
            SELECT id, tag
            FROM data_element
            WHERE edition_id = ?
              AND (
                lower(name) = lower(?)
                OR lower(keyword) = lower(?)
                OR tag = ?
              )
            ORDER BY is_range, tag
            LIMIT 1
            """,
            (edition, candidate, candidate, candidate),
        ).fetchone()
        if row is not None:
            return cast(sqlite3.Row, row)
    return _data_element_mentioned_in_text(
        connection,
        edition=edition,
        section_text=section_text,
    )


def _data_element_mentioned_in_text(
    connection: sqlite3.Connection,
    *,
    edition: str,
    section_text: str | None,
) -> sqlite3.Row | None:
    if not section_text:
        return None
    compact_text = _compact_value(section_text)
    matches: list[tuple[int, sqlite3.Row]] = []
    for row in connection.execute(
        """
        SELECT id, tag, name
        FROM data_element
        WHERE edition_id = ?
        ORDER BY tag
        """,
        (edition,),
    ):
        needle = _compact_value(f"{row['name']} {row['tag']}")
        index = compact_text.find(needle)
        if index >= 0:
            matches.append((index, row))
    if not matches:
        return None
    return sorted(matches, key=lambda match: match[0])[0][1]


def _compact_value(value: str) -> str:
    return re.sub(r"\s+", "", normalize_text(value)).lower()


def _attribute_use_ids_for_term_context(
    connection: sqlite3.Connection,
    *,
    edition: str,
    data_element_id: str,
    data_element_tag: str,
    parent_xml_id: str | None,
) -> tuple[str, ...]:
    if parent_xml_id is None:
        return ()
    rows = connection.execute(
        """
        SELECT au.id
        FROM attribute_use au
        JOIN source_ref sr ON sr.id = au.source_ref_id
        WHERE au.edition_id = ?
          AND au.attribute_tag = ?
          AND sr.section = ?
        ORDER BY au.id
        """,
        (edition, data_element_tag, parent_xml_id),
    ).fetchall()
    if rows:
        return tuple(str(row["id"]) for row in rows)

    global_rows = connection.execute(
        """
        SELECT au.id
        FROM attribute_use au
        JOIN data_element de
          ON de.edition_id = au.edition_id
         AND de.tag = au.attribute_tag
        WHERE au.edition_id = ?
          AND de.id = ?
        ORDER BY au.id
        """,
        (edition, data_element_id),
    ).fetchall()
    if len(global_rows) == 1:
        return (str(global_rows[0]["id"]),)
    return ()


def _value_term_context_label(
    variablelist: ParsedVariableList, *, section_title: str | None
) -> str | None:
    if section_title and variablelist.title:
        return f"{section_title} - {variablelist.title}"
    return variablelist.title or section_title or variablelist.parent_xml_id


def _value_term_source_ref_id(
    edition: str, part: str, variablelist: ParsedVariableList
) -> str:
    return f"{edition}.{part}.value_terms.{variablelist.xml_id or variablelist.ordinal}"


def _value_term_id(
    edition: str,
    part: str,
    variablelist: ParsedVariableList,
    entry_index: int,
    term_index: int,
    context_index: int,
) -> str:
    return (
        f"{edition}.{part}.attribute_value_term."
        f"{variablelist.xml_id or variablelist.ordinal}."
        f"{entry_index}.{term_index}.{context_index}"
    )


def _insert_service_class(
    connection: sqlite3.Connection, service_class: ServiceClass
) -> None:
    connection.execute(
        """
        INSERT INTO service_class (
          id, edition_id, name, section, source_ref_id
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            service_class.id,
            service_class.edition_id,
            service_class.name,
            service_class.section,
            service_class.source_ref.id,
        ),
    )


def _insert_sop_class(connection: sqlite3.Connection, sop_class: SOPClass) -> None:
    connection.execute(
        """
        INSERT INTO sop_class (
          id, edition_id, name, uid_value, service_class_id, source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            sop_class.id,
            sop_class.edition_id,
            sop_class.name,
            sop_class.uid_value,
            sop_class.service_class_id,
            sop_class.source_ref.id,
        ),
    )


def _insert_sop_class_iod(
    connection: sqlite3.Connection, sop_class_iod: SOPClassIOD
) -> None:
    connection.execute(
        """
        INSERT INTO sop_class_iod (
          id, edition_id, sop_class_id, iod_id, resolution, resolution_warning,
          source_ref_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            sop_class_iod.id,
            sop_class_iod.edition_id,
            sop_class_iod.sop_class_id,
            sop_class_iod.iod_id,
            sop_class_iod.resolution,
            sop_class_iod.resolution_warning,
            sop_class_iod.source_ref.id,
        ),
    )

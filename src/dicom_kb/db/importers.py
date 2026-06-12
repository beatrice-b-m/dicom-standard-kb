"""Transactional import of parsed IR records into SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    DataElement,
    IODFunctionalGroupUse,
    IODModuleUse,
    Macro,
    Module,
    SourceRef,
    UIDRegistryEntry,
)
from dicom_kb.sources.manifest import SourceManifest


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
) -> ImportSummary:
    """Import parsed PS3.3 graph records transactionally."""
    iod_records = tuple(iods)
    module_records = tuple(modules)
    macro_records = tuple(macros)
    module_use_records = tuple(iod_module_uses)
    functional_group_use_records = tuple(iod_functional_group_uses)
    attribute_use_records = tuple(attribute_uses)
    source_refs = _unique_source_refs(
        [record.source_ref for record in iod_records]
        + [record.source_ref for record in module_records]
        + [record.source_ref for record in macro_records]
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
    )


def _unique_source_refs(source_refs: Iterable[SourceRef]) -> tuple[SourceRef, ...]:
    unique: dict[str, SourceRef] = {}
    for source_ref in source_refs:
        unique[source_ref.id] = source_ref
    return tuple(unique.values())


def _insert_source_ref(connection: sqlite3.Connection, source_ref: SourceRef) -> None:
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
            source_ref.canonical_url,
        ),
    )


def _insert_data_element(
    connection: sqlite3.Connection, element: DataElement
) -> None:
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

"""PS3.3 and PS3.4 graph import."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from dicom_kb.db.importers._shared import (
    ImportSummary,
    _insert_source_ref,
    _unique_source_refs,
)
from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    Condition,
    IODFunctionalGroupUse,
    IODModuleUse,
    Macro,
    Module,
    ServiceClass,
    SOPClass,
    SOPClassIOD,
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

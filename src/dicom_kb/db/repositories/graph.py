"""PS3.3 and PS3.4 graph storage lookups."""

from __future__ import annotations

import sqlite3

from dicom_kb.db.repositories._rows import (
    _attribute_use_from_prefixed_row,
    _condition_from_prefixed_row,
    _iod_from_prefixed_row,
    _iod_from_row,
    _iod_functional_group_use_from_prefixed_row,
    _iod_module_use_from_prefixed_row,
    _macro_from_prefixed_row,
    _macro_from_row,
    _module_from_prefixed_row,
    _module_from_row,
    _service_class_from_prefixed_row,
    _sop_class_from_prefixed_row,
    _sop_class_iod_from_prefixed_row,
)
from dicom_kb.db.repositories.records import (
    AttributeUseRecord,
    IODFunctionalGroupUseRecord,
    IODModuleUseRecord,
    SOPClassIODRecord,
)
from dicom_kb.ir.models import (
    IOD,
    Macro,
    Module,
    ServiceClass,
    SOPClass,
)


class Part03Repository:
    """Lookup and traverse imported PS3.3 IOD/module/macro graph records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_iod_by_name_or_keyword(
        self, name_or_keyword: str, *, edition: str
    ) -> IOD | None:
        """Return an IOD by exact name or keyword."""
        row = self.connection.execute(
            """
            SELECT i.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM iod i
            JOIN source_ref sr ON sr.id = i.source_ref_id
            WHERE i.edition_id = ?
              AND (lower(i.name) = lower(?) OR lower(i.keyword) = lower(?))
            """,
            (edition, name_or_keyword, name_or_keyword),
        ).fetchone()
        return _iod_from_row(row) if row else None

    def find_module_by_name(self, name: str, *, edition: str) -> Module | None:
        """Return a module by exact name."""
        row = self.connection.execute(
            """
            SELECT m.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM module m
            JOIN source_ref sr ON sr.id = m.source_ref_id
            WHERE m.edition_id = ? AND lower(m.name) = lower(?)
            ORDER BY m.section IS NULL, m.section
            LIMIT 1
            """,
            (edition, name),
        ).fetchone()
        return _module_from_row(row) if row else None

    def find_macro_by_name_or_table(
        self, name_or_table: str, *, edition: str
    ) -> Macro | None:
        """Return a macro by exact name or table/xml id."""
        row = self.connection.execute(
            """
            SELECT m.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM macro m
            JOIN source_ref sr ON sr.id = m.source_ref_id
            WHERE m.edition_id = ?
              AND (lower(m.name) = lower(?) OR lower(m.table_id) = lower(?))
            """,
            (edition, name_or_table, name_or_table),
        ).fetchone()
        return _macro_from_row(row) if row else None

    def list_module_uses_for_iod(
        self, iod_id: str, *, edition: str
    ) -> list[IODModuleUseRecord]:
        """Return modules listed by an IOD in table order."""
        rows = self.connection.execute(
            """
            SELECT
              imu.id AS use_id,
              imu.edition_id AS use_edition_id,
              imu.iod_id AS use_iod_id,
              imu.information_entity AS use_information_entity,
              imu.module_id AS use_module_id,
              imu.usage AS use_usage,
              imu.usage_condition_text AS use_usage_condition_text,
              imu.condition_id AS use_condition_id,
              imu.source_ref_id AS use_source_ref_id,
              use_sr.part AS use_source_part,
              use_sr.section AS use_source_section,
              use_sr.table_id AS use_source_table_id,
              use_sr.xml_id AS use_source_xml_id,
              use_sr.title AS use_source_title,
              use_sr.canonical_url AS use_source_url,
              m.id AS module_id,
              m.edition_id AS module_edition_id,
              m.name AS module_name,
              m.section AS module_section,
              m.description AS module_description,
              m.source_ref_id AS module_source_ref_id,
              module_sr.part AS module_source_part,
              module_sr.section AS module_source_section,
              module_sr.table_id AS module_source_table_id,
              module_sr.xml_id AS module_source_xml_id,
              module_sr.title AS module_source_title,
              module_sr.canonical_url AS module_source_url,
              c.id AS condition_id,
              c.edition_id AS condition_edition_id,
              c.condition_kind AS condition_condition_kind,
              c.raw_text AS condition_raw_text,
              c.normalized_text AS condition_normalized_text,
              c.machine_status AS condition_machine_status,
              c.expression_json AS condition_expression_json,
              c.source_ref_id AS condition_source_ref_id,
              condition_sr.part AS condition_source_part,
              condition_sr.section AS condition_source_section,
              condition_sr.table_id AS condition_source_table_id,
              condition_sr.xml_id AS condition_source_xml_id,
              condition_sr.title AS condition_source_title,
              condition_sr.canonical_url AS condition_source_url
            FROM iod_module_use imu
            JOIN module m ON m.id = imu.module_id
            JOIN source_ref use_sr ON use_sr.id = imu.source_ref_id
            JOIN source_ref module_sr ON module_sr.id = m.source_ref_id
            LEFT JOIN condition c ON c.id = imu.condition_id
            LEFT JOIN source_ref condition_sr ON condition_sr.id = c.source_ref_id
            WHERE imu.edition_id = ? AND imu.iod_id = ?
            ORDER BY imu.id
            """,
            (edition, iod_id),
        ).fetchall()
        return [
            IODModuleUseRecord(
                use=_iod_module_use_from_prefixed_row(row),
                module=_module_from_prefixed_row(row, "module"),
                condition=(
                    _condition_from_prefixed_row(row, "condition")
                    if row["condition_id"] is not None
                    else None
                ),
            )
            for row in sorted(rows, key=lambda row: _id_order(str(row["use_id"])))
        ]

    def list_functional_group_uses_for_iod(
        self, iod_id: str, *, edition: str
    ) -> list[IODFunctionalGroupUseRecord]:
        """Return functional-group macros listed by an IOD in table order."""
        rows = self.connection.execute(
            """
            SELECT
              fg.id AS use_id,
              fg.edition_id AS use_edition_id,
              fg.iod_id AS use_iod_id,
              fg.macro_id AS use_macro_id,
              fg.usage AS use_usage,
              fg.usage_condition_text AS use_usage_condition_text,
              fg.condition_id AS use_condition_id,
              fg.source_ref_id AS use_source_ref_id,
              use_sr.part AS use_source_part,
              use_sr.section AS use_source_section,
              use_sr.table_id AS use_source_table_id,
              use_sr.xml_id AS use_source_xml_id,
              use_sr.title AS use_source_title,
              use_sr.canonical_url AS use_source_url,
              m.id AS macro_id,
              m.edition_id AS macro_edition_id,
              m.name AS macro_name,
              m.table_id AS macro_table_id,
              m.section AS macro_section,
              m.macro_kind AS macro_macro_kind,
              m.source_ref_id AS macro_source_ref_id,
              macro_sr.part AS macro_source_part,
              macro_sr.section AS macro_source_section,
              macro_sr.table_id AS macro_source_table_id,
              macro_sr.xml_id AS macro_source_xml_id,
              macro_sr.title AS macro_source_title,
              macro_sr.canonical_url AS macro_source_url,
              c.id AS condition_id,
              c.edition_id AS condition_edition_id,
              c.condition_kind AS condition_condition_kind,
              c.raw_text AS condition_raw_text,
              c.normalized_text AS condition_normalized_text,
              c.machine_status AS condition_machine_status,
              c.expression_json AS condition_expression_json,
              c.source_ref_id AS condition_source_ref_id,
              condition_sr.part AS condition_source_part,
              condition_sr.section AS condition_source_section,
              condition_sr.table_id AS condition_source_table_id,
              condition_sr.xml_id AS condition_source_xml_id,
              condition_sr.title AS condition_source_title,
              condition_sr.canonical_url AS condition_source_url
            FROM iod_functional_group_use fg
            JOIN macro m ON m.id = fg.macro_id
            JOIN source_ref use_sr ON use_sr.id = fg.source_ref_id
            JOIN source_ref macro_sr ON macro_sr.id = m.source_ref_id
            LEFT JOIN condition c ON c.id = fg.condition_id
            LEFT JOIN source_ref condition_sr ON condition_sr.id = c.source_ref_id
            WHERE fg.edition_id = ? AND fg.iod_id = ?
            ORDER BY fg.id
            """,
            (edition, iod_id),
        ).fetchall()
        return [
            IODFunctionalGroupUseRecord(
                use=_iod_functional_group_use_from_prefixed_row(row),
                macro=_macro_from_prefixed_row(row, "macro"),
                condition=(
                    _condition_from_prefixed_row(row, "condition")
                    if row["condition_id"] is not None
                    else None
                ),
            )
            for row in sorted(rows, key=lambda row: _id_order(str(row["use_id"])))
        ]

    def list_attribute_uses(
        self, *, owner_type: str, owner_id: str, edition: str
    ) -> list[AttributeUseRecord]:
        """Return attribute rows for a module or macro in table order."""
        rows = self.connection.execute(
            """
            SELECT
              au.id AS attribute_id,
              au.edition_id AS attribute_edition_id,
              au.owner_type AS attribute_owner_type,
              au.owner_id AS attribute_owner_id,
              au.parent_attribute_use_id AS attribute_parent_attribute_use_id,
              au.row_kind AS attribute_row_kind,
              au.attribute_tag AS attribute_attribute_tag,
              au.attribute_keyword AS attribute_attribute_keyword,
              au.attribute_name AS attribute_attribute_name,
              au.type_designation AS attribute_type_designation,
              au.description_text AS attribute_description_text,
              au.condition_id AS attribute_condition_id,
              au.included_macro_id AS attribute_included_macro_id,
              au.include_target_text AS attribute_include_target_text,
              au.sequence_depth AS attribute_sequence_depth,
              au.row_order AS attribute_row_order,
              au.source_ref_id AS attribute_source_ref_id,
              attr_sr.part AS attribute_source_part,
              attr_sr.section AS attribute_source_section,
              attr_sr.table_id AS attribute_source_table_id,
              attr_sr.xml_id AS attribute_source_xml_id,
              attr_sr.title AS attribute_source_title,
              attr_sr.canonical_url AS attribute_source_url,
              im.id AS macro_id,
              im.edition_id AS macro_edition_id,
              im.name AS macro_name,
              im.table_id AS macro_table_id,
              im.section AS macro_section,
              im.macro_kind AS macro_macro_kind,
              im.source_ref_id AS macro_source_ref_id,
              macro_sr.part AS macro_source_part,
              macro_sr.section AS macro_source_section,
              macro_sr.table_id AS macro_source_table_id,
              macro_sr.xml_id AS macro_source_xml_id,
              macro_sr.title AS macro_source_title,
              macro_sr.canonical_url AS macro_source_url,
              c.id AS condition_id,
              c.edition_id AS condition_edition_id,
              c.condition_kind AS condition_condition_kind,
              c.raw_text AS condition_raw_text,
              c.normalized_text AS condition_normalized_text,
              c.machine_status AS condition_machine_status,
              c.expression_json AS condition_expression_json,
              c.source_ref_id AS condition_source_ref_id,
              condition_sr.part AS condition_source_part,
              condition_sr.section AS condition_source_section,
              condition_sr.table_id AS condition_source_table_id,
              condition_sr.xml_id AS condition_source_xml_id,
              condition_sr.title AS condition_source_title,
              condition_sr.canonical_url AS condition_source_url
            FROM attribute_use au
            JOIN source_ref attr_sr ON attr_sr.id = au.source_ref_id
            LEFT JOIN macro im ON im.id = au.included_macro_id
            LEFT JOIN source_ref macro_sr ON macro_sr.id = im.source_ref_id
            LEFT JOIN condition c ON c.id = au.condition_id
            LEFT JOIN source_ref condition_sr ON condition_sr.id = c.source_ref_id
            WHERE au.edition_id = ?
              AND au.owner_type = ?
              AND au.owner_id = ?
            ORDER BY au.row_order
            """,
            (edition, owner_type, owner_id),
        ).fetchall()
        owner_name = self._owner_name(owner_type, owner_id, edition=edition)
        return [
            AttributeUseRecord(
                attribute_use=_attribute_use_from_prefixed_row(row),
                owner_type=owner_type,
                owner_name=owner_name,
                included_macro=(
                    _macro_from_prefixed_row(row, "macro")
                    if row["macro_id"] is not None
                    else None
                ),
                condition=(
                    _condition_from_prefixed_row(row, "condition")
                    if row["condition_id"] is not None
                    else None
                ),
            )
            for row in rows
        ]

    def _owner_name(self, owner_type: str, owner_id: str, *, edition: str) -> str:
        if owner_type == "module":
            module = self.find_module_by_id(owner_id, edition=edition)
            return module.name if module else owner_id
        if owner_type == "macro":
            macro = self.find_macro_by_id(owner_id, edition=edition)
            return macro.name if macro else owner_id
        return owner_id

    def find_module_by_id(self, module_id: str, *, edition: str) -> Module | None:
        row = self.connection.execute(
            """
            SELECT m.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM module m
            JOIN source_ref sr ON sr.id = m.source_ref_id
            WHERE m.edition_id = ? AND m.id = ?
            """,
            (edition, module_id),
        ).fetchone()
        return _module_from_row(row) if row else None

    def find_macro_by_id(self, macro_id: str, *, edition: str) -> Macro | None:
        row = self.connection.execute(
            """
            SELECT m.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM macro m
            JOIN source_ref sr ON sr.id = m.source_ref_id
            WHERE m.edition_id = ? AND m.id = ?
            """,
            (edition, macro_id),
        ).fetchone()
        return _macro_from_row(row) if row else None


class Part04Repository:
    """Lookup and traverse imported PS3.4 service/SOP Class records."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_sop_class_by_uid_or_name(
        self, uid_or_name: str, *, edition: str
    ) -> tuple[SOPClass, ServiceClass | None] | None:
        """Return a SOP Class by UID value, name, or PS3.6 UID keyword."""
        row = self.connection.execute(
            """
            SELECT
              sc.id AS sop_id,
              sc.edition_id AS sop_edition_id,
              sc.name AS sop_name,
              sc.uid_value AS sop_uid_value,
              sc.service_class_id AS sop_service_class_id,
              sc.source_ref_id AS sop_source_ref_id,
              sop_sr.part AS sop_source_part,
              sop_sr.section AS sop_source_section,
              sop_sr.table_id AS sop_source_table_id,
              sop_sr.xml_id AS sop_source_xml_id,
              sop_sr.title AS sop_source_title,
              sop_sr.canonical_url AS sop_source_url,
              svc.id AS service_id,
              svc.edition_id AS service_edition_id,
              svc.name AS service_name,
              svc.section AS service_section,
              svc.source_ref_id AS service_source_ref_id,
              service_sr.part AS service_source_part,
              service_sr.section AS service_source_section,
              service_sr.table_id AS service_source_table_id,
              service_sr.xml_id AS service_source_xml_id,
              service_sr.title AS service_source_title,
              service_sr.canonical_url AS service_source_url
            FROM sop_class sc
            JOIN source_ref sop_sr ON sop_sr.id = sc.source_ref_id
            LEFT JOIN service_class svc ON svc.id = sc.service_class_id
            LEFT JOIN source_ref service_sr ON service_sr.id = svc.source_ref_id
            LEFT JOIN uid_registry_entry uid
              ON uid.edition_id = sc.edition_id AND uid.uid_value = sc.uid_value
            WHERE sc.edition_id = ?
              AND (
                sc.uid_value = ?
                OR lower(sc.name) = lower(?)
                OR lower(uid.uid_keyword) = lower(?)
              )
            """,
            (edition, uid_or_name, uid_or_name, uid_or_name),
        ).fetchone()
        if row is None:
            return None
        return (
            _sop_class_from_prefixed_row(row, "sop"),
            (
                _service_class_from_prefixed_row(row, "service")
                if row["service_id"] is not None
                else None
            ),
        )

    def list_iods_for_sop_class(
        self, sop_class_id: str, *, edition: str
    ) -> list[SOPClassIODRecord]:
        """Return IODs linked to a SOP Class in parsed table order."""
        rows = self.connection.execute(
            """
            SELECT
              sci.id AS edge_id,
              sci.edition_id AS edge_edition_id,
              sci.sop_class_id AS edge_sop_class_id,
              sci.iod_id AS edge_iod_id,
              sci.resolution AS edge_resolution,
              sci.resolution_warning AS edge_resolution_warning,
              sci.source_ref_id AS edge_source_ref_id,
              edge_sr.part AS edge_source_part,
              edge_sr.section AS edge_source_section,
              edge_sr.table_id AS edge_source_table_id,
              edge_sr.xml_id AS edge_source_xml_id,
              edge_sr.title AS edge_source_title,
              edge_sr.canonical_url AS edge_source_url,
              i.id AS iod_id,
              i.edition_id AS iod_edition_id,
              i.name AS iod_name,
              i.keyword AS iod_keyword,
              i.iod_type AS iod_iod_type,
              i.part AS iod_part,
              i.section AS iod_section,
              i.source_ref_id AS iod_source_ref_id,
              iod_sr.part AS iod_source_part,
              iod_sr.section AS iod_source_section,
              iod_sr.table_id AS iod_source_table_id,
              iod_sr.xml_id AS iod_source_xml_id,
              iod_sr.title AS iod_source_title,
              iod_sr.canonical_url AS iod_source_url
            FROM sop_class_iod sci
            JOIN source_ref edge_sr ON edge_sr.id = sci.source_ref_id
            JOIN iod i ON i.id = sci.iod_id
            JOIN source_ref iod_sr ON iod_sr.id = i.source_ref_id
            WHERE sci.edition_id = ? AND sci.sop_class_id = ?
            ORDER BY sci.id
            """,
            (edition, sop_class_id),
        ).fetchall()
        return [
            SOPClassIODRecord(
                edge=_sop_class_iod_from_prefixed_row(row, "edge"),
                iod=_iod_from_prefixed_row(row, "iod"),
            )
            for row in sorted(rows, key=lambda row: _id_order(str(row["edge_id"])))
        ]


def _id_order(value: str) -> int:
    suffix = value.rsplit(".", maxsplit=1)[-1]
    return int(suffix) if suffix.isdigit() else 0

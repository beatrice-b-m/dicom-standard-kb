"""SQLite repositories for exact deterministic lookups."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import cast

from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    DataElement,
    IODModuleUse,
    Macro,
    Module,
    ServiceClass,
    SOPClass,
    SOPClassIOD,
    SourceRef,
    UIDRegistryEntry,
)
from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag, tag_matches


@dataclass(frozen=True)
class IODModuleUseRecord:
    """A module-use edge joined to its module definition."""

    use: IODModuleUse
    module: Module


@dataclass(frozen=True)
class AttributeUseRecord:
    """An attribute-use row with query-time expansion context."""

    attribute_use: AttributeUse
    owner_type: str
    owner_name: str
    included_macro: Macro | None = None
    expanded_from_include: AttributeUse | None = None


@dataclass(frozen=True)
class SOPClassIODRecord:
    """A SOP Class to IOD edge joined to the target IOD."""

    edge: SOPClassIOD
    iod: IOD


class DataElementRepository:
    """Lookup PS3.6 data elements by tag or keyword."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_tag_or_keyword(
        self, tag_or_keyword: str, *, edition: str
    ) -> tuple[DataElement | None, str | None]:
        """Return an exact record and optional range-match warning."""
        try:
            tag = normalize_tag(tag_or_keyword)
        except IdentifierValidationError:
            row = self.connection.execute(
                """
                SELECT de.*, sr.part AS source_part, sr.section AS source_section,
                       sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                       sr.title AS source_title, sr.canonical_url AS source_url
                FROM data_element de
                JOIN source_ref sr ON sr.id = de.source_ref_id
                WHERE de.edition_id = ? AND lower(de.keyword) = lower(?)
                """,
                (edition, tag_or_keyword),
            ).fetchone()
            return (_data_element_from_row(row) if row else None), None

        row = self._find_exact_tag(tag, edition)
        if row is not None:
            return _data_element_from_row(row), None

        for candidate in self._range_rows(edition):
            if tag_matches(str(candidate["tag"]), tag):
                warning = f"concrete tag {tag} matched range row {candidate['tag']}"
                return _data_element_from_row(candidate), warning
        return None, None

    def _find_exact_tag(self, tag: str, edition: str) -> sqlite3.Row | None:
        row = self.connection.execute(
            """
            SELECT de.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM data_element de
            JOIN source_ref sr ON sr.id = de.source_ref_id
            WHERE de.edition_id = ? AND de.tag = ?
            """,
            (edition, tag),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    def _range_rows(self, edition: str) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT de.*, sr.part AS source_part, sr.section AS source_section,
                       sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                       sr.title AS source_title, sr.canonical_url AS source_url
                FROM data_element de
                JOIN source_ref sr ON sr.id = de.source_ref_id
                WHERE de.edition_id = ? AND de.is_range = 1
                """,
                (edition,),
            )
        )


class UIDRepository:
    """Lookup PS3.6 UID registry entries by UID value or keyword."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def find_by_uid_or_keyword(
        self, uid_or_keyword: str, *, edition: str
    ) -> UIDRegistryEntry | None:
        """Return a UID registry entry by value or keyword."""
        row = self.connection.execute(
            """
            SELECT uid.*, sr.part AS source_part, sr.section AS source_section,
                   sr.table_id AS source_table_id, sr.xml_id AS source_xml_id,
                   sr.title AS source_title, sr.canonical_url AS source_url
            FROM uid_registry_entry uid
            JOIN source_ref sr ON sr.id = uid.source_ref_id
            WHERE uid.edition_id = ?
              AND (uid.uid_value = ? OR lower(uid.uid_keyword) = lower(?))
            """,
            (edition, uid_or_keyword, uid_or_keyword),
        ).fetchone()
        return _uid_from_row(row) if row else None


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
              module_sr.canonical_url AS module_source_url
            FROM iod_module_use imu
            JOIN module m ON m.id = imu.module_id
            JOIN source_ref use_sr ON use_sr.id = imu.source_ref_id
            JOIN source_ref module_sr ON module_sr.id = m.source_ref_id
            WHERE imu.edition_id = ? AND imu.iod_id = ?
            ORDER BY imu.id
            """,
            (edition, iod_id),
        ).fetchall()
        return [
            IODModuleUseRecord(
                use=_iod_module_use_from_prefixed_row(row),
                module=_module_from_prefixed_row(row, "module"),
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
              macro_sr.canonical_url AS macro_source_url
            FROM attribute_use au
            JOIN source_ref attr_sr ON attr_sr.id = au.source_ref_id
            LEFT JOIN macro im ON im.id = au.included_macro_id
            LEFT JOIN source_ref macro_sr ON macro_sr.id = im.source_ref_id
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


def _source_ref_from_row(row: sqlite3.Row) -> SourceRef:
    return SourceRef(
        id=str(row["source_ref_id"]),
        edition_id=str(row["edition_id"]),
        part=str(row["source_part"]),
        section=row["source_section"],
        table_id=row["source_table_id"],
        xml_id=row["source_xml_id"],
        title=row["source_title"],
        canonical_url=row["source_url"],
    )


def _data_element_from_row(row: sqlite3.Row) -> DataElement:
    return DataElement(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        tag=str(row["tag"]),
        group_pattern=str(row["group_pattern"]),
        element_pattern=str(row["element_pattern"]),
        is_range=bool(row["is_range"]),
        name=str(row["name"]),
        keyword=row["keyword"],
        vr=row["vr"],
        vm=row["vm"],
        retired=bool(row["retired"]),
        retired_in_or_last_seen=row["retired_in_or_last_seen"],
        source_ref=_source_ref_from_row(row),
    )


def _uid_from_row(row: sqlite3.Row) -> UIDRegistryEntry:
    return UIDRegistryEntry(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        uid_value=str(row["uid_value"]),
        uid_name=str(row["uid_name"]),
        uid_keyword=row["uid_keyword"],
        uid_type=str(row["uid_type"]),
        part=row["part"],
        retired=bool(row["retired"]),
        retired_in_or_last_seen=row["retired_in_or_last_seen"],
        source_ref=_source_ref_from_row(row),
    )


def _id_order(value: str) -> int:
    suffix = value.rsplit(".", maxsplit=1)[-1]
    return int(suffix) if suffix.isdigit() else 0


def _iod_from_row(row: sqlite3.Row) -> IOD:
    return IOD(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        name=str(row["name"]),
        keyword=row["keyword"],
        iod_type=row["iod_type"],
        part=str(row["part"]),
        section=row["section"],
        source_ref=_source_ref_from_row(row),
    )


def _module_from_row(row: sqlite3.Row) -> Module:
    return Module(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        name=str(row["name"]),
        section=row["section"],
        description=row["description"],
        source_ref=_source_ref_from_row(row),
    )


def _macro_from_row(row: sqlite3.Row) -> Macro:
    return Macro(
        id=str(row["id"]),
        edition_id=str(row["edition_id"]),
        name=str(row["name"]),
        table_id=row["table_id"],
        section=row["section"],
        macro_kind=row["macro_kind"],
        source_ref=_source_ref_from_row(row),
    )


def _source_ref_from_prefixed_row(row: sqlite3.Row, prefix: str) -> SourceRef:
    return SourceRef(
        id=str(row[f"{prefix}_source_ref_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        part=str(row[f"{prefix}_source_part"]),
        section=row[f"{prefix}_source_section"],
        table_id=row[f"{prefix}_source_table_id"],
        xml_id=row[f"{prefix}_source_xml_id"],
        title=row[f"{prefix}_source_title"],
        canonical_url=row[f"{prefix}_source_url"],
    )


def _module_from_prefixed_row(row: sqlite3.Row, prefix: str) -> Module:
    return Module(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        section=row[f"{prefix}_section"],
        description=row[f"{prefix}_description"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _macro_from_prefixed_row(row: sqlite3.Row, prefix: str) -> Macro:
    return Macro(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        table_id=row[f"{prefix}_table_id"],
        section=row[f"{prefix}_section"],
        macro_kind=row[f"{prefix}_macro_kind"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _service_class_from_prefixed_row(row: sqlite3.Row, prefix: str) -> ServiceClass:
    return ServiceClass(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        section=row[f"{prefix}_section"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _sop_class_from_prefixed_row(row: sqlite3.Row, prefix: str) -> SOPClass:
    return SOPClass(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        uid_value=str(row[f"{prefix}_uid_value"]),
        service_class_id=row[f"{prefix}_service_class_id"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _iod_from_prefixed_row(row: sqlite3.Row, prefix: str) -> IOD:
    return IOD(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        name=str(row[f"{prefix}_name"]),
        keyword=row[f"{prefix}_keyword"],
        iod_type=row[f"{prefix}_iod_type"],
        part=str(row[f"{prefix}_part"]),
        section=row[f"{prefix}_section"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _iod_module_use_from_prefixed_row(row: sqlite3.Row) -> IODModuleUse:
    return IODModuleUse(
        id=str(row["use_id"]),
        edition_id=str(row["use_edition_id"]),
        iod_id=str(row["use_iod_id"]),
        information_entity=row["use_information_entity"],
        module_id=str(row["use_module_id"]),
        usage=str(row["use_usage"]),
        usage_condition_text=row["use_usage_condition_text"],
        condition_id=row["use_condition_id"],
        source_ref=_source_ref_from_prefixed_row(row, "use"),
    )


def _sop_class_iod_from_prefixed_row(row: sqlite3.Row, prefix: str) -> SOPClassIOD:
    return SOPClassIOD(
        id=str(row[f"{prefix}_id"]),
        edition_id=str(row[f"{prefix}_edition_id"]),
        sop_class_id=str(row[f"{prefix}_sop_class_id"]),
        iod_id=str(row[f"{prefix}_iod_id"]),
        resolution=str(row[f"{prefix}_resolution"]),
        resolution_warning=row[f"{prefix}_resolution_warning"],
        source_ref=_source_ref_from_prefixed_row(row, prefix),
    )


def _attribute_use_from_prefixed_row(row: sqlite3.Row) -> AttributeUse:
    return AttributeUse(
        id=str(row["attribute_id"]),
        edition_id=str(row["attribute_edition_id"]),
        owner_type=str(row["attribute_owner_type"]),
        owner_id=str(row["attribute_owner_id"]),
        parent_attribute_use_id=row["attribute_parent_attribute_use_id"],
        row_kind=str(row["attribute_row_kind"]),
        attribute_tag=row["attribute_attribute_tag"],
        attribute_keyword=row["attribute_attribute_keyword"],
        attribute_name=row["attribute_attribute_name"],
        type_designation=row["attribute_type_designation"],
        description_text=row["attribute_description_text"],
        condition_id=row["attribute_condition_id"],
        included_macro_id=row["attribute_included_macro_id"],
        include_target_text=row["attribute_include_target_text"],
        sequence_depth=int(row["attribute_sequence_depth"]),
        row_order=int(row["attribute_row_order"]),
        source_ref=_source_ref_from_prefixed_row(row, "attribute"),
    )

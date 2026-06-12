"""Public response contracts shared by CLI and future agent tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from dicom_kb.db.repositories import (
    AttributeUseRecord,
    IODModuleUseRecord,
    SOPClassIODRecord,
)
from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    DataElement,
    DocNode,
    Module,
    ServiceClass,
    SOPClass,
    SourceRef,
    UIDRegistryEntry,
)

NOTICE = "Consult the official DICOM Standard for authoritative text."

ResponseStatus = Literal["ok", "not_found", "validation_error"]


class StandardRef(BaseModel):
    """Citation pointer for a standard fact."""

    model_config = ConfigDict(frozen=True)

    part: str
    section: str | None = None
    table: str | None = None
    anchor: str | None = None
    official_url: str | None = None
    edition: str


class ResponseTrace(BaseModel):
    """Trace metadata for deterministic tool execution."""

    model_config = ConfigDict(frozen=True)

    query_id: str = Field(default_factory=lambda: str(uuid4()))
    resolved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_manifest_sha256: str | None = None


class ToolResponse(BaseModel):
    """Common envelope for all public query tools."""

    model_config = ConfigDict(frozen=True)

    edition: str
    tool: str
    input: dict[str, str]
    status: ResponseStatus
    result: dict[str, Any] | None
    refs: list[StandardRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    notice: str = NOTICE
    trace: ResponseTrace = Field(default_factory=ResponseTrace)


def data_element_result(element: DataElement) -> dict[str, Any]:
    """Return the public result payload for a data element."""
    return {
        "tag": element.tag,
        "name": element.name,
        "keyword": element.keyword,
        "vr": element.vr,
        "vm": element.vm,
        "retired": element.retired,
    }


def uid_result(uid: UIDRegistryEntry) -> dict[str, Any]:
    """Return the public result payload for a UID registry entry."""
    return {
        "uid_value": uid.uid_value,
        "uid_name": uid.uid_name,
        "uid_keyword": uid.uid_keyword,
        "uid_type": uid.uid_type,
        "part": uid.part,
        "retired": uid.retired,
    }


def iod_modules_result(iod: IOD, records: list[IODModuleUseRecord]) -> dict[str, Any]:
    """Return the public result payload for an IOD module traversal."""
    return {
        "iod": {
            "id": iod.id,
            "name": iod.name,
            "keyword": iod.keyword,
            "iod_type": iod.iod_type,
            "section": iod.section,
        },
        "modules": [
            {
                "module_id": record.module.id,
                "module_name": record.module.name,
                "section": record.module.section,
                "information_entity": record.use.information_entity,
                "usage": record.use.usage,
                "usage_condition_text": record.use.usage_condition_text,
            }
            for record in records
        ],
    }


def iod_result(iod: IOD) -> dict[str, Any]:
    """Return the public result payload for an IOD."""
    return {
        "id": iod.id,
        "name": iod.name,
        "keyword": iod.keyword,
        "iod_type": iod.iod_type,
        "part": iod.part,
        "section": iod.section,
    }


def sop_class_result(
    sop_class: SOPClass,
    service_class: ServiceClass | None,
    iod_records: list[SOPClassIODRecord],
) -> dict[str, Any]:
    """Return the public result payload for a SOP Class traversal."""
    return {
        "sop_class": {
            "id": sop_class.id,
            "name": sop_class.name,
            "uid_value": sop_class.uid_value,
        },
        "service_class": (
            {
                "id": service_class.id,
                "name": service_class.name,
                "section": service_class.section,
            }
            if service_class is not None
            else None
        ),
        "iods": [
            {
                "iod_id": record.iod.id,
                "iod_name": record.iod.name,
                "iod_keyword": record.iod.keyword,
                "resolution": record.edge.resolution,
                "resolution_warning": record.edge.resolution_warning,
            }
            for record in iod_records
        ],
    }


def module_attributes_result(
    module: Module, records: list[AttributeUseRecord]
) -> dict[str, Any]:
    """Return the public result payload for a module attribute traversal."""
    return {
        "module": {
            "id": module.id,
            "name": module.name,
            "section": module.section,
        },
        "attributes": [_attribute_use_result(record) for record in records],
    }


def attribute_context_result(
    element: DataElement,
    uses: list[dict[str, Any]],
    *,
    effective_type: str | None,
    effective_type_explanation: str,
) -> dict[str, Any]:
    """Return the public result payload for an attribute-in-context traversal."""
    return {
        "attribute": data_element_result(element),
        "uses": uses,
        "effective_type": effective_type,
        "effective_type_explanation": effective_type_explanation,
    }


def standard_text_result(
    node: DocNode,
    tables: list[DocNode],
    *,
    text_excerpt: str,
) -> dict[str, Any]:
    """Return the public result payload for a short standard text excerpt."""
    return {
        "part": node.part,
        "section": node.number or node.xml_id,
        "title": node.title,
        "text_excerpt": text_excerpt,
        "tables": [
            {
                "table_id": table.xml_id,
                "title": table.title,
            }
            for table in tables
        ],
    }


def standard_ref(source_ref: SourceRef) -> StandardRef:
    """Convert an internal source ref to the public citation shape."""
    return StandardRef(
        part=source_ref.part,
        section=source_ref.section,
        table=source_ref.title or source_ref.table_id,
        anchor=source_ref.xml_id,
        official_url=source_ref.canonical_url,
        edition=source_ref.edition_id,
    )


def _attribute_use_result(record: AttributeUseRecord) -> dict[str, Any]:
    attribute = record.attribute_use
    payload: dict[str, Any] = {
        "id": attribute.id,
        "row_kind": attribute.row_kind,
        "owner_type": record.owner_type,
        "owner_name": record.owner_name,
        "sequence_depth": attribute.sequence_depth,
        "row_order": attribute.row_order,
    }
    if attribute.row_kind == "include":
        payload.update(
            {
                "include_target_text": attribute.include_target_text,
                "included_macro_id": attribute.included_macro_id,
                "included_macro_name": (
                    record.included_macro.name if record.included_macro else None
                ),
            }
        )
    else:
        payload.update(_attribute_fact_payload(attribute))
    if record.expanded_from_include is not None:
        payload["expanded_from_include_id"] = record.expanded_from_include.id
    return payload


def _attribute_fact_payload(attribute: AttributeUse) -> dict[str, Any]:
    return {
        "attribute_tag": attribute.attribute_tag,
        "attribute_keyword": attribute.attribute_keyword,
        "attribute_name": attribute.attribute_name,
        "type_designation": attribute.type_designation,
        "description_text": attribute.description_text,
        "parent_attribute_use_id": attribute.parent_attribute_use_id,
    }

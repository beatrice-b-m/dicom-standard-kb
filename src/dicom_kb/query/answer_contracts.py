"""Public response contracts shared by CLI and future agent tools."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from dicom_kb.ir.models import DataElement, SourceRef, UIDRegistryEntry

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


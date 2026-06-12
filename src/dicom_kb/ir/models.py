"""Canonical records shared by parsers, storage, and queries."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class SourceRef(BaseModel):
    """A compact source reference attached to parsed facts."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    part: str
    section: str | None = None
    table_id: str | None = None
    xml_id: str | None = None
    title: str | None = None
    canonical_url: str | None = None


class DataElement(BaseModel):
    """PS3.6 data element registry row."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    tag: str
    group_pattern: str
    element_pattern: str
    is_range: bool
    name: str
    keyword: str | None
    vr: str | None
    vm: str | None
    retired: bool
    retired_in_or_last_seen: str | None = None
    source_ref: SourceRef


class UIDRegistryEntry(BaseModel):
    """PS3.6 UID registry row."""

    model_config = ConfigDict(frozen=True)

    id: str
    edition_id: str
    uid_value: str
    uid_name: str
    uid_keyword: str | None
    uid_type: str
    part: str | None
    retired: bool
    retired_in_or_last_seen: str | None = None
    source_ref: SourceRef


class ParserWarning(BaseModel):
    """Structured parser warning."""

    model_config = ConfigDict(frozen=True)

    part: str
    table_id: str | None
    row_index: int | None
    message: str

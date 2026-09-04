"""VR and transfer syntax evidence and encoding explanations."""

from __future__ import annotations

import sqlite3
from datetime import datetime

from dicom_kb.db.repositories import (
    DocumentRepository,
    Part05Repository,
)
from dicom_kb.ir.models import (
    TransferSyntaxDetail,
    VRDefinition,
)
from dicom_kb.ir.validators import (
    IdentifierValidationError,
    normalize_uid,
)
from dicom_kb.query.answer_contracts import (
    ToolResponse,
    encoding_rule_explanation_result,
    standard_ref,
    tool_response,
    transfer_syntax_detail_result,
    vr_definition_result,
)
from dicom_kb.query.citations import build_trace, citation_refs
from dicom_kb.query.resolver._identifiers import _looks_like_uid
from dicom_kb.query.search import build_fts_query


def lookup_vr(
    connection: sqlite3.Connection,
    *,
    vr: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a PS3.5 Value Representation definition by VR code."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"vr": vr}
    normalized_vr = vr.strip().upper()
    if not _is_vr_code(normalized_vr):
        return tool_response(
            edition=edition,
            tool="lookup_vr",
            input=response_input,
            status="validation_error",
            result={"message": "vr must be a two-letter DICOM VR code."},
            trace=trace,
        )

    definition = Part05Repository(connection).find_vr(normalized_vr, edition=edition)
    if definition is None:
        return tool_response(
            edition=edition,
            tool="lookup_vr",
            input=response_input,
            status="not_found",
            result={"message": "No PS3.5 VR definition matched the input."},
            trace=trace,
        )

    return tool_response(
        edition=edition,
        tool="lookup_vr",
        input=response_input,
        status="ok",
        result=vr_definition_result(
            vr=definition.vr,
            name=definition.name,
            value_representation_class=definition.value_representation_class,
            length_notes=list(definition.length_notes),
            padding_behavior=definition.padding_behavior,
            character_repertoire_notes=list(definition.character_repertoire_notes),
            binary_or_text=definition.binary_or_text,
        ),
        refs=[standard_ref(definition.source_ref)],
        trace=trace,
    )


def lookup_transfer_syntax(
    connection: sqlite3.Connection,
    *,
    uid_or_keyword: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Resolve a transfer syntax UID with deterministic encoding details."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"uid_or_keyword": uid_or_keyword}
    if _looks_like_uid(uid_or_keyword):
        try:
            normalize_uid(uid_or_keyword)
        except IdentifierValidationError as exc:
            return tool_response(
                edition=edition,
                tool="lookup_transfer_syntax",
                input=response_input,
                status="validation_error",
                result={"message": str(exc)},
                trace=trace,
            )

    record = Part05Repository(connection).find_transfer_syntax(
        uid_or_keyword,
        edition=edition,
    )
    if record is None:
        return tool_response(
            edition=edition,
            tool="lookup_transfer_syntax",
            input=response_input,
            status="not_found",
            result={"message": "No transfer syntax detail matched the input."},
            trace=trace,
        )

    return tool_response(
        edition=edition,
        tool="lookup_transfer_syntax",
        input=response_input,
        status="ok",
        result=transfer_syntax_detail_result(
            uid_value=record.uid.uid_value,
            uid_name=record.uid.uid_name,
            uid_keyword=record.uid.uid_keyword,
            explicit_vr=record.detail.explicit_vr,
            endian=record.detail.endian,
            encapsulated=record.detail.encapsulated,
            compression_family=record.detail.compression_family,
            retired=record.uid.retired,
            encoding_notes=list(record.detail.encoding_notes),
        ),
        refs=citation_refs(
            (record.uid.source_ref,),
            (record.detail.source_ref,),
        ),
        trace=trace,
    )


def explain_encoding_rule(
    connection: sqlite3.Connection,
    *,
    topic: str,
    edition: str,
    query_id: str | None = None,
    resolved_at: datetime | None = None,
) -> ToolResponse:
    """Explain a PS3.5 encoding topic using parsed rows or cited text."""
    trace = build_trace(
        connection,
        edition=edition,
        query_id=query_id,
        resolved_at=resolved_at,
    )
    response_input = {"topic": topic}
    normalized_topic = topic.strip()
    if not normalized_topic:
        return tool_response(
            edition=edition,
            tool="explain_encoding_rule",
            input=response_input,
            status="validation_error",
            result={"message": "topic must not be empty."},
            trace=trace,
        )

    repository = Part05Repository(connection)
    normalized_vr = normalized_topic.upper()
    if _is_vr_code(normalized_vr):
        definition = repository.find_vr(normalized_vr, edition=edition)
        if definition is not None:
            return tool_response(
                edition=edition,
                tool="explain_encoding_rule",
                input=response_input,
                status="ok",
                result=encoding_rule_explanation_result(
                    topic=topic,
                    summary=f"{definition.vr} is the {definition.name} VR.",
                    structured_facts=_vr_structured_facts(definition),
                ),
                refs=[standard_ref(definition.source_ref)],
                trace=trace,
            )

    transfer_syntax = repository.find_transfer_syntax(
        normalized_topic,
        edition=edition,
    )
    if transfer_syntax is not None:
        return tool_response(
            edition=edition,
            tool="explain_encoding_rule",
            input=response_input,
            status="ok",
            result=encoding_rule_explanation_result(
                topic=topic,
                summary=(
                    f"{transfer_syntax.uid.uid_name} is a transfer syntax "
                    "with parsed encoding details."
                ),
                structured_facts=_transfer_syntax_structured_facts(
                    transfer_syntax.detail
                ),
            ),
            refs=citation_refs(
                (transfer_syntax.uid.source_ref,),
                (transfer_syntax.detail.source_ref,),
            ),
            trace=trace,
        )

    fts_query = build_fts_query(normalized_topic)
    if fts_query is None:
        return tool_response(
            edition=edition,
            tool="explain_encoding_rule",
            input=response_input,
            status="validation_error",
            result={"message": "topic must contain at least one searchable term."},
            trace=trace,
        )

    matches = DocumentRepository(connection).search_text(
        fts_query=fts_query,
        edition=edition,
        part_filter="PS3.5",
        limit=1,
    )
    if not matches:
        return tool_response(
            edition=edition,
            tool="explain_encoding_rule",
            input=response_input,
            status="not_found",
            result={"message": "No PS3.5 encoding rule matched the topic."},
            trace=trace,
        )

    match = matches[0]
    excerpt = (match.node.plain_text or match.snippet)[:800]
    return tool_response(
        edition=edition,
        tool="explain_encoding_rule",
        input=response_input,
        status="ok",
        result=encoding_rule_explanation_result(
            topic=topic,
            summary=f"Retrieved PS3.5 text for {normalized_topic}.",
            text_excerpt=excerpt,
        ),
        refs=[standard_ref(match.node.source_ref)],
        trace=trace,
    )


def _is_vr_code(value: str) -> bool:
    return len(value) == 2 and value.isalpha() and value.isupper()


def _vr_structured_facts(definition: VRDefinition) -> list[str]:
    facts = [f"name: {definition.name}"]
    if definition.value_representation_class is not None:
        facts.append(
            f"value representation class: {definition.value_representation_class}"
        )
    if definition.binary_or_text is not None:
        facts.append(f"binary or text: {definition.binary_or_text}")
    if definition.padding_behavior is not None:
        facts.append(f"padding behavior: {definition.padding_behavior}")
    facts.extend(f"length note: {note}" for note in definition.length_notes)
    facts.extend(
        f"character repertoire note: {note}"
        for note in definition.character_repertoire_notes
    )
    return facts


def _transfer_syntax_structured_facts(
    detail: TransferSyntaxDetail,
) -> list[str]:
    facts: list[str] = []
    if detail.explicit_vr is not None:
        facts.append(f"explicit VR: {str(detail.explicit_vr).lower()}")
    if detail.endian is not None:
        facts.append(f"endian: {detail.endian}")
    if detail.encapsulated is not None:
        facts.append(f"encapsulated: {str(detail.encapsulated).lower()}")
    if detail.compression_family is not None:
        facts.append(f"compression family: {detail.compression_family}")
    facts.extend(f"encoding note: {note}" for note in detail.encoding_notes)
    return facts

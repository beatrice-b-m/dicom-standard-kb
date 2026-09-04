"""Joined query records shared by repository domains."""

from __future__ import annotations

from dataclasses import dataclass

from dicom_kb.ir.models import (
    IOD,
    AttributeUse,
    AttributeValueTerm,
    CodedConcept,
    Condition,
    ContextGroup,
    ContextGroupRow,
    DataElement,
    DocNode,
    IODFunctionalGroupUse,
    IODModuleUse,
    Macro,
    Module,
    SOPClassIOD,
    SRTemplate,
    SRTemplateRow,
    TransferSyntaxDetail,
    UIDRegistryEntry,
)


@dataclass(frozen=True)
class IODModuleUseRecord:
    """A module-use edge joined to its module definition."""

    use: IODModuleUse
    module: Module
    condition: Condition | None = None


@dataclass(frozen=True)
class IODFunctionalGroupUseRecord:
    """A functional-group-use edge joined to its macro definition."""

    use: IODFunctionalGroupUse
    macro: Macro
    condition: Condition | None = None


@dataclass(frozen=True)
class AttributeUseRecord:
    """An attribute-use row with query-time expansion context."""

    attribute_use: AttributeUse
    owner_type: str
    owner_name: str
    included_macro: Macro | None = None
    condition: Condition | None = None
    expanded_from_include: AttributeUse | None = None
    macro_path: tuple[str, ...] = ()


@dataclass(frozen=True)
class SOPClassIODRecord:
    """A SOP Class to IOD edge joined to the target IOD."""

    edge: SOPClassIOD
    iod: IOD


@dataclass(frozen=True)
class DocumentSearchResult:
    """A matched DocBook node with a short full-text search snippet."""

    node: DocNode
    snippet: str


@dataclass(frozen=True)
class AttributeValueTermRecord:
    """A value term joined to its optional PS3.6 data element."""

    term: AttributeValueTerm
    data_element: DataElement | None = None


@dataclass(frozen=True)
class TransferSyntaxDetailRecord:
    """A transfer-syntax detail row joined to its PS3.6 UID registry entry."""

    detail: TransferSyntaxDetail
    uid: UIDRegistryEntry


@dataclass(frozen=True)
class CodeMeaningRecord:
    """A coded concept with context groups that cite the same code."""

    concept: CodedConcept
    context_groups: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextGroupRecord:
    """A PS3.16 context group with ordered coded and include rows."""

    group: ContextGroup
    rows: tuple[ContextGroupRow, ...] = ()


@dataclass(frozen=True)
class SRTemplateRecord:
    """A PS3.16 SR template with ordered content and include rows."""

    template: SRTemplate
    rows: tuple[SRTemplateRow, ...] = ()

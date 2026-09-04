"""Stable imports for SQLite repositories."""

from dicom_kb.db.repositories.documents import DocumentRepository
from dicom_kb.db.repositories.graph import Part03Repository, Part04Repository
from dicom_kb.db.repositories.media import Part10Repository, Part18Repository
from dicom_kb.db.repositories.records import (
    AttributeUseRecord,
    AttributeValueTermRecord,
    CodeMeaningRecord,
    ContextGroupRecord,
    DocumentSearchResult,
    IODFunctionalGroupUseRecord,
    IODModuleUseRecord,
    SOPClassIODRecord,
    SRTemplateRecord,
    TransferSyntaxDetailRecord,
)
from dicom_kb.db.repositories.registry import (
    DataElementRepository,
    Part05Repository,
    UIDRepository,
)
from dicom_kb.db.repositories.terminology import Part16Repository
from dicom_kb.db.repositories.value_terms import AttributeValueTermRepository

__all__ = [
    "AttributeUseRecord",
    "AttributeValueTermRecord",
    "AttributeValueTermRepository",
    "CodeMeaningRecord",
    "ContextGroupRecord",
    "DataElementRepository",
    "DocumentRepository",
    "DocumentSearchResult",
    "IODFunctionalGroupUseRecord",
    "IODModuleUseRecord",
    "Part03Repository",
    "Part04Repository",
    "Part05Repository",
    "Part10Repository",
    "Part16Repository",
    "Part18Repository",
    "SOPClassIODRecord",
    "SRTemplateRecord",
    "TransferSyntaxDetailRecord",
    "UIDRepository",
]

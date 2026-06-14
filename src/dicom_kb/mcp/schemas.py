"""Schema and metadata definitions for MCP tool registration."""

from __future__ import annotations

from typing import Literal, TypedDict

MCPToolName = Literal[
    "dicom_lookup_data_element",
    "dicom_lookup_uid",
    "dicom_lookup_sop_class",
    "dicom_lookup_iod",
    "dicom_lookup_enumerated_values",
    "dicom_lookup_defined_terms",
    "dicom_lookup_vr",
    "dicom_lookup_transfer_syntax",
    "dicom_explain_encoding_rule",
    "dicom_lookup_media_type",
    "dicom_lookup_dicomweb_transaction",
    "dicom_lookup_sr_template",
    "dicom_list_modules_for_iod",
    "dicom_list_attributes_for_module",
    "dicom_resolve_attribute_context",
    "dicom_retrieve_standard_text",
    "dicom_search_standard_text",
]

MCP_TOOL_NAMES: tuple[MCPToolName, ...] = (
    "dicom_lookup_data_element",
    "dicom_lookup_uid",
    "dicom_lookup_sop_class",
    "dicom_lookup_iod",
    "dicom_lookup_enumerated_values",
    "dicom_lookup_defined_terms",
    "dicom_lookup_vr",
    "dicom_lookup_transfer_syntax",
    "dicom_explain_encoding_rule",
    "dicom_lookup_media_type",
    "dicom_lookup_dicomweb_transaction",
    "dicom_lookup_sr_template",
    "dicom_list_modules_for_iod",
    "dicom_list_attributes_for_module",
    "dicom_resolve_attribute_context",
    "dicom_retrieve_standard_text",
    "dicom_search_standard_text",
)


class MCPToolSpec(TypedDict):
    """Static MCP tool metadata used during registration."""

    name: MCPToolName
    description: str


MCP_TOOL_SPECS: tuple[MCPToolSpec, ...] = (
    {
        "name": "dicom_lookup_data_element",
        "description": (
            "Look up a DICOM PS3.6 data element by tag, range tag, or keyword."
        ),
    },
    {
        "name": "dicom_lookup_uid",
        "description": "Look up a DICOM PS3.6 UID registry entry by UID or keyword.",
    },
    {
        "name": "dicom_lookup_sop_class",
        "description": "Look up a DICOM PS3.4 SOP Class and linked IOD records.",
    },
    {
        "name": "dicom_lookup_iod",
        "description": "Look up a DICOM PS3.3 IOD by name or keyword.",
    },
    {
        "name": "dicom_lookup_enumerated_values",
        "description": "Look up parsed DICOM enumerated values for an attribute.",
    },
    {
        "name": "dicom_lookup_defined_terms",
        "description": "Look up parsed DICOM defined terms for an attribute.",
    },
    {
        "name": "dicom_lookup_vr",
        "description": "Look up a DICOM PS3.5 Value Representation definition.",
    },
    {
        "name": "dicom_lookup_transfer_syntax",
        "description": (
            "Look up a DICOM transfer syntax UID with PS3.5 encoding details."
        ),
    },
    {
        "name": "dicom_explain_encoding_rule",
        "description": "Explain a DICOM PS3.5 encoding rule with citations.",
    },
    {
        "name": "dicom_lookup_media_type",
        "description": (
            "Look up PS3.10 DICOM media-type constraints by media type or context."
        ),
    },
    {
        "name": "dicom_lookup_dicomweb_transaction",
        "description": (
            "Look up a PS3.18 DICOMweb transaction by name or route template."
        ),
    },
    {
        "name": "dicom_lookup_sr_template",
        "description": "Look up a DICOM PS3.16 SR template by TID or name.",
    },
    {
        "name": "dicom_list_modules_for_iod",
        "description": "List PS3.3 modules used by an IOD.",
    },
    {
        "name": "dicom_list_attributes_for_module",
        "description": "List PS3.3 attribute rows for a module.",
    },
    {
        "name": "dicom_resolve_attribute_context",
        "description": "Resolve a DICOM attribute's effective PS3.3 type in context.",
    },
    {
        "name": "dicom_retrieve_standard_text",
        "description": "Retrieve a capped excerpt from persisted DICOM standard text.",
    },
    {
        "name": "dicom_search_standard_text",
        "description": "Search persisted DICOM standard text.",
    },
)

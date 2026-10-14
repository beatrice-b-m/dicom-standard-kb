"""Schema and metadata definitions for MCP tool registration."""

from __future__ import annotations

from typing import Literal, TypedDict

MCPToolName = Literal[
    "dicom_lookup_uid",
    "dicom_lookup_enumerated_values",
    "dicom_lookup_defined_terms",
    "dicom_lookup_vr",
    "dicom_lookup_transfer_syntax",
    "dicom_explain_encoding_rule",
    "dicom_lookup_media_type",
    "dicom_lookup_dicomweb_transaction",
    "dicom_lookup_sr_template",
    "dicom_lookup_context_group",
    "dicom_lookup_code_meaning",
    "dicom_element",
    "dicom_iod",
    "dicom_module",
    "dicom_search",
    "dicom_read",
]

MCP_TOOL_NAMES: tuple[MCPToolName, ...] = (
    "dicom_lookup_uid",
    "dicom_lookup_enumerated_values",
    "dicom_lookup_defined_terms",
    "dicom_lookup_vr",
    "dicom_lookup_transfer_syntax",
    "dicom_explain_encoding_rule",
    "dicom_lookup_media_type",
    "dicom_lookup_dicomweb_transaction",
    "dicom_lookup_sr_template",
    "dicom_lookup_context_group",
    "dicom_lookup_code_meaning",
    "dicom_element",
    "dicom_iod",
    "dicom_module",
    "dicom_search",
    "dicom_read",
)


class MCPToolSpec(TypedDict):
    """Static MCP tool metadata used during registration."""

    name: MCPToolName
    description: str


MCP_TOOL_SPECS: tuple[MCPToolSpec, ...] = (
    {
        "name": "dicom_lookup_uid",
        "description": "Look up a DICOM PS3.6 UID registry entry by UID or keyword.",
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
        "name": "dicom_lookup_context_group",
        "description": "Look up a DICOM PS3.16 context group by CID or name.",
    },
    {
        "name": "dicom_lookup_code_meaning",
        "description": (
            "Look up a DICOM PS3.16 coded concept by code value and optional scheme."
        ),
    },
    {
        "name": "dicom_element",
        "description": (
            "Look up a data element by tag, keyword or name: VR, VM, retired "
            "status, and the PS3.3 modules and macros that use it with their "
            "Type. Pass iod to get its Type, nesting and conditions in one IOD."
        ),
    },
    {
        "name": "dicom_iod",
        "description": (
            "Look up an IOD by name, or by SOP Class name, UID or keyword: its "
            "SOP Classes and its modules with usage (M, C with the condition, "
            "U), plus functional group macros for multi-frame IODs. With "
            "expand=true, every attribute of every module with macros "
            "expanded: the checklist for building or validating an instance. "
            "Long answers come in pages; pass page to continue."
        ),
    },
    {
        "name": "dicom_module",
        "description": (
            "List a module's or macro's attributes with included macros "
            "expanded in place: keyword, tag, VR, VM, Type and the full "
            "description. Takes a name ('General Series', 'Code Sequence "
            "Macro') or a table ('Table C.7-5a'). Long answers come in pages; "
            "pass page to continue."
        ),
    },
    {
        "name": "dicom_search",
        "description": (
            "Search every part of the DICOM standard. Returns ranked sections "
            "and tables, normative text first, each with a ref to pass to "
            "dicom_read. Optional part narrows it, e.g. PS3.5."
        ),
    },
    {
        "name": "dicom_read",
        "description": (
            "Read a section or table of the DICOM standard as markdown with "
            "every reference resolved, e.g. 'PS3.5 7.5.2', 'Table C.7-5a', "
            "'PS3.3 Annex A', 'CID 7010'. Long nodes come in pages; pass page "
            "to continue."
        ),
    },
)

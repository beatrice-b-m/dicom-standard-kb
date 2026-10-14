"""Schema and metadata definitions for MCP tool registration."""

from __future__ import annotations

from typing import Literal, TypedDict

MCPToolName = Literal[
    "dicom_element",
    "dicom_iod",
    "dicom_module",
    "dicom_values",
    "dicom_code",
    "dicom_search",
    "dicom_read",
]

MCP_TOOL_NAMES: tuple[MCPToolName, ...] = (
    "dicom_element",
    "dicom_iod",
    "dicom_module",
    "dicom_values",
    "dicom_code",
    "dicom_search",
    "dicom_read",
)


class MCPToolSpec(TypedDict):
    """Static MCP tool metadata used during registration."""

    name: MCPToolName
    description: str


MCP_TOOL_SPECS: tuple[MCPToolSpec, ...] = (
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
            "expand=true, the attributes of its M and C modules with macros "
            "expanded: the checklist for building or validating an instance. "
            "Narrow it with type ('required' for 1/1C/2/2C, or e.g. '1,1C'; a "
            "row counts only if its enclosing sequences match too), usage "
            "('M,C,U' adds U modules) or module (one or more module names). "
            "The answer ends with what was left out. Long answers come in "
            "pages; pass page to continue."
        ),
    },
    {
        "name": "dicom_module",
        "description": (
            "A module's or macro's attributes: keyword, tag, VR, VM, Type and "
            "description. By default an outline: the module's own rows, each "
            "included macro as one line with its size, descriptions cut to "
            "the first sentence and condition. detail='full' expands macros in "
            "place with full descriptions. type ('required', or e.g. '1,1C') "
            "keeps those Types, macros expanded. Takes a name ('General "
            "Series', 'Code Sequence Macro') or a table ('Table C.7-5a'). Long "
            "answers come in pages; pass page to continue."
        ),
    },
    {
        "name": "dicom_values",
        "description": (
            "What an attribute may hold: its enumerated values and defined "
            "terms with their meanings, and for a code sequence the context "
            "groups (BCID/DCID) each module names for it. Takes a tag, keyword "
            "or name. Pass within (an IOD, module or macro, e.g. 'CT Image') "
            "to keep only what applies there. Long answers come in pages."
        ),
    },
    {
        "name": "dicom_code",
        "description": (
            "PS3.16 terminology. 'CID 4031' lists a context group's codes with "
            "included groups expanded; 'TID 1500' reads a template; a code "
            "('121071', '(121071, DCM)' or code with scheme) gives its meaning, "
            "DCM definition and the groups that list it. Group, template or "
            "code meaning names work too. Long answers come in pages."
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
            "'PS3.3 Annex A', 'CID 7010'. Also reads a UID or UID keyword from "
            "the PS3.6 registry (a transfer syntax adds its VR, byte order, "
            "Pixel Data encoding and the PS3.5 section with its rules) and a "
            "VR code such as 'OB' (its PS3.5 definition and header layout). "
            "Long nodes come in pages; pass page to continue."
        ),
    },
)

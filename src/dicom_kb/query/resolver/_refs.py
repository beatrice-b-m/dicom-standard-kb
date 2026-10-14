"""How answers name a node of the standard so dicom_read can find it again."""

from __future__ import annotations

from dicom_kb.docbook.targets import Target
from dicom_kb.ir.models import DocNode
from dicom_kb.query.answer_contracts import StandardRef


def _target(node: DocNode) -> Target:
    return Target(
        part=node.part,
        xml_id=node.xml_id or node.id,
        kind=node.node_type,
        label=node.number,
        title=node.title,
    )


def _reference(node: DocNode) -> str:
    """The text a caller passes back to `dicom_read` for this node."""
    target = _target(node)
    if node.number and (_has_canonical_id(node) or node.xml_id is None):
        if target.globally_unique:
            return target.name
        return f"{node.part} {target.name}"
    # A label that disagrees with the id may be shared with another node
    # (TID 300 and its parameter table), so the id is the safe handle.
    return f"{node.part} {node.xml_id or node.title or ''}".strip()


_ID_PREFIXES = {"chapter": "chapter_", "section": "sect_", "table": "table_"}


def _has_canonical_id(node: DocNode) -> bool:
    prefix = _ID_PREFIXES.get(node.node_type)
    if prefix is None or node.number is None or node.xml_id is None:
        return True
    label = node.number.replace(" ", "_")
    return node.xml_id in {prefix + label, f"{prefix}{node.part}_{label}"}


def node_ref(node: DocNode, edition: str) -> StandardRef:
    """Cite a node by the same name `dicom_read` takes."""
    label = _reference(node)
    return StandardRef(
        label=label if label.startswith(node.part) else f"{node.part} {label}",
        part=node.part,
        section=node.xml_id,
        table=node.xml_id if node.node_type == "table" else None,
        anchor=node.xml_id,
        edition=edition,
    )

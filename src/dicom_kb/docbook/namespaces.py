"""DocBook namespace constants and XPath helpers."""

from __future__ import annotations

DOCBOOK_NS = "http://docbook.org/ns/docbook"
XML_NS = "http://www.w3.org/XML/1998/namespace"

NSMAP = {"db": DOCBOOK_NS, "xml": XML_NS}


def xml_id_name() -> str:
    """Return the Clark-notation XML ID attribute name."""
    return f"{{{XML_NS}}}id"

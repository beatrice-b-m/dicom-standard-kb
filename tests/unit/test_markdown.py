from dicom_kb.query.answer_contracts import StandardRef, tool_response
from dicom_kb.query.markdown import render_markdown, source_line
from tests.fixtures_synthetic import EDITION


def _ref(part: str, anchor: str | None, section: str | None = None) -> StandardRef:
    return StandardRef(part=part, anchor=anchor, section=section, edition=EDITION)


def test_source_line_names_tables_sections_and_cids() -> None:
    refs = [
        _ref("PS3.3", "table_C.7-9"),
        _ref("PS3.3", None, section="sect_C.7.3.1"),
        _ref("PS3.16", "sect_CID_29"),
        _ref("PS3.16", "table_TID_1500"),
        _ref("PS3.3", "table_C.7-9"),
    ]

    assert source_line(refs) == (
        "Source: PS3.3 Table C.7-9; PS3.3 C.7.3.1; PS3.16 CID 29; "
        f"PS3.16 TID 1500 ({EDITION})"
    )


def test_source_line_caps_long_lists() -> None:
    refs = [_ref("PS3.3", f"table_C.{index}-1") for index in range(8)]

    assert source_line(refs).endswith(f"Table C.4-1 and 3 more ({EDITION})")


def test_hits_drop_empty_columns_and_escape_pipes() -> None:
    response = tool_response(
        status="ok",
        result={
            "hits": [
                {"Ref": "PS3.5 A.4", "Title": "a|b", "Context": ""},
                {"Ref": "PS3.5 A.4.1", "Title": "c", "Context": None},
            ]
        },
    )

    assert render_markdown(response) == (
        "| Ref | Title |\n|---|---|\n| PS3.5 A.4 | a\\|b |\n| PS3.5 A.4.1 | c |\n"
    )


def test_not_found_lists_candidates() -> None:
    response = tool_response(
        status="not_found",
        result={
            "message": "C.8.8 names more than one section.",
            "candidates": [{"Ref": "PS3.3 C.8.8", "Title": "RT Series Module"}],
        },
    )

    assert render_markdown(response) == (
        "C.8.8 names more than one section.\n\nCandidates:\n"
        "| Ref | Title |\n|---|---|\n| PS3.3 C.8.8 | RT Series Module |\n"
    )

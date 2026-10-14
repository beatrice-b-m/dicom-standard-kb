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


def test_tables_drop_internal_ids_and_empty_columns_and_escape_pipes() -> None:
    response = tool_response(
        status="ok",
        result={
            "items": [
                {"id": f"{EDITION}.x.1", "name": "a|b", "unused": None},
                {"id": f"{EDITION}.x.2", "name": "c", "unused": ""},
            ]
        },
    )

    assert render_markdown(response) == "**Items**\n| Name |\n|---|\n| a\\|b |\n| c |\n"


def test_not_found_lists_candidates() -> None:
    response = tool_response(
        status="validation_error",
        result={
            "message": "Matched multiple contexts.",
            "candidates": [{"media_type": "application/dicom"}],
        },
    )

    assert render_markdown(response) == (
        "Matched multiple contexts.\n\nCandidates:\n"
        "| Media type |\n|---|\n| application/dicom |\n"
    )

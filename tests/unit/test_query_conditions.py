from __future__ import annotations

from dicom_kb.query.conditions import AttributeContextMatch, effective_type_summary


def _match(
    type_designation: str,
    *,
    description_text: str | None = None,
    condition_text: str | None = None,
    source_ref_id: str = "source-a",
) -> AttributeContextMatch:
    return AttributeContextMatch(
        payload={"attribute_use_id": source_ref_id},
        type_designation=type_designation,
        description_text=description_text,
        condition_text=condition_text,
        source_ref_id=source_ref_id,
    )


def test_effective_type_uses_lowest_type_when_no_override_text() -> None:
    effective_type, explanation, warnings = effective_type_summary(
        [
            _match("2", description_text="Patient name."),
            _match("1", description_text="Duplicate contextual use."),
        ]
    )

    assert effective_type == "1"
    assert explanation.startswith("Multiple applicable uses")
    assert warnings == []


def test_effective_type_uses_single_explicit_override() -> None:
    effective_type, explanation, warnings = effective_type_summary(
        [
            _match("2", description_text="Patient name."),
            _match(
                "1",
                description_text="This attribute shall be Type 3 in this module.",
                source_ref_id="source-b",
            ),
        ]
    )

    assert effective_type == "3"
    assert explanation == (
        "Explicit type override language selected Type 3 from source refs: source-b."
    )
    assert warnings == []


def test_effective_type_withholds_conflicting_explicit_overrides() -> None:
    effective_type, explanation, warnings = effective_type_summary(
        [
            _match(
                "2",
                description_text="This attribute shall be Type 2 in this module.",
                source_ref_id="source-a",
            ),
            _match(
                "1",
                condition_text="This attribute shall be Type 1 in this module.",
                source_ref_id="source-b",
            ),
        ]
    )

    assert effective_type is None
    assert explanation == (
        "Conflicting explicit type override language was found in matched row text."
    )
    assert warnings == [
        "conflicting explicit type overrides found: Type 2 in source-a, "
        "Type 1 in source-b"
    ]


def test_effective_type_withholds_ambiguous_override_language() -> None:
    effective_type, explanation, warnings = effective_type_summary(
        [
            _match("2", description_text="Patient name."),
            _match(
                "1",
                description_text=(
                    "This row may be Type 1 or Type 2 depending on acquisition."
                ),
                source_ref_id="source-b",
            ),
        ]
    )

    assert effective_type is None
    assert explanation == (
        "Ambiguous type override language was found in matched row text."
    )
    assert warnings == [
        "ambiguous type override language found in source refs: source-b"
    ]

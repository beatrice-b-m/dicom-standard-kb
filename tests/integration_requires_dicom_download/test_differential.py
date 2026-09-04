from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from dicom_kb.ir.validators import IdentifierValidationError, normalize_tag

ALLOWLIST_PATH = Path(__file__).with_name("differential_allowlist.json")
DATA_ELEMENT_FIELDS = ("name", "keyword", "vr", "vm", "retired")
DIFF_CLASSIFICATIONS = {"parser_issue", "interpretation_issue", "edition_skew"}
DATA_ELEMENT_GOLDEN_TAGS = {
    "(0008,0060)",
    "(0008,0016)",
    "(0008,0018)",
    "(7FE0,0010)",
    "(0002,0010)",
    "(0010,0010)",
    "(0020,000D)",
    "(0020,000E)",
}


def test_ps36_data_elements_match_pydicom_dictionary(
    connection: sqlite3.Connection, edition: str
) -> None:
    external_elements = _load_pydicom_data_elements()
    local_elements = _local_data_elements(connection, edition=edition)
    compared_tags = sorted(set(local_elements) & set(external_elements))
    if not DATA_ELEMENT_GOLDEN_TAGS.issubset(external_elements):
        missing = sorted(DATA_ELEMENT_GOLDEN_TAGS - set(external_elements))
        pytest.fail(f"pydicom data dictionary does not include golden tags: {missing}")
    if not compared_tags:
        pytest.skip("no overlapping PS3.6 data elements found in pydicom")

    allowlist = _load_allowlist()
    mismatches: list[dict[str, object]] = []
    for tag in compared_tags:
        local = local_elements[tag]
        external = external_elements[tag]
        for field in DATA_ELEMENT_FIELDS:
            local_value = local.get(field)
            external_value = external.get(field)
            if external_value is None or local_value == external_value:
                continue
            mismatch = {
                "external": "pydicom",
                "entity_type": "data_element",
                "id": tag,
                "field": field,
                "local": local_value,
                "external_value": external_value,
            }
            if not _is_allowlisted(mismatch, allowlist):
                mismatches.append(mismatch)

    assert not mismatches, json.dumps(mismatches, indent=2, sort_keys=True)


def test_ps36_data_elements_match_innolitics_json(
    connection: sqlite3.Connection, edition: str
) -> None:
    source_path = _innolitics_path()
    external_elements = _load_innolitics_data_elements(source_path)
    if not external_elements:
        pytest.skip(f"no parseable Innolitics data elements found in {source_path}")

    local_elements = _local_data_elements(connection, edition=edition)
    compared_tags = sorted(set(local_elements) & set(external_elements))
    if not DATA_ELEMENT_GOLDEN_TAGS.issubset(external_elements):
        missing = sorted(DATA_ELEMENT_GOLDEN_TAGS - set(external_elements))
        pytest.fail(f"Innolitics data does not include golden tags: {missing}")
    if not compared_tags:
        pytest.skip(f"no overlapping PS3.6 data elements found in {source_path}")

    allowlist = _load_allowlist()
    mismatches: list[dict[str, object]] = []
    for tag in compared_tags:
        local = local_elements[tag]
        external = external_elements[tag]
        for field in DATA_ELEMENT_FIELDS:
            local_value = local.get(field)
            external_value = external.get(field)
            if external_value is None or local_value == external_value:
                continue
            mismatch = {
                "external": "innolitics",
                "entity_type": "data_element",
                "id": tag,
                "field": field,
                "local": local_value,
                "external_value": external_value,
            }
            if not _is_allowlisted(mismatch, allowlist):
                mismatches.append(mismatch)

    assert not mismatches, json.dumps(mismatches, indent=2, sort_keys=True)


def test_ct_image_module_list_matches_innolitics_json(
    connection: sqlite3.Connection, edition: str
) -> None:
    source_path = _innolitics_path()
    external_modules = _load_innolitics_ct_modules(source_path)
    if not external_modules:
        pytest.skip(
            f"no parseable Innolitics CT Image module list found in {source_path}"
        )

    local_modules = {
        _normalize_module_name(row["name"])
        for row in connection.execute(
            """
            SELECT m.name
            FROM iod_module_use imu
            JOIN iod i ON i.id = imu.iod_id
            JOIN module m ON m.id = imu.module_id
            WHERE imu.edition_id = ?
              AND lower(i.name) = lower('CT Image')
            """,
            (edition,),
        )
    }
    allowlist = _load_allowlist()
    mismatch = {
        "external": "innolitics",
        "entity_type": "iod_modules",
        "id": "CT Image",
        "field": "modules",
        "local": sorted(local_modules),
        "external_value": sorted(external_modules),
    }
    if local_modules != external_modules and not _is_allowlisted(mismatch, allowlist):
        pytest.fail(json.dumps(mismatch, indent=2, sort_keys=True))


def _innolitics_path() -> Path:
    configured = os.environ.get("DICOM_KB_INNOLITICS_PATH")
    if not configured:
        pytest.skip(
            "set DICOM_KB_INNOLITICS_PATH to an Innolitics JSON file or directory "
            "to run differential comparisons"
        )
    path = Path(configured).expanduser()
    if not path.exists():
        pytest.skip(f"DICOM_KB_INNOLITICS_PATH does not exist: {path}")
    return path


def _load_innolitics_data_elements(path: Path) -> dict[str, dict[str, object]]:
    elements: dict[str, dict[str, object]] = {}
    for item in _walk_json_files(path):
        tag_text = _first_text(item, "tag", "Tag")
        if tag_text is None:
            continue
        try:
            tag = normalize_tag(tag_text)
        except IdentifierValidationError:
            continue
        candidate = {
            "name": _strip_retired_parenthetical(
                _first_text(item, "name", "Name", "title")
            ),
            "keyword": _first_text(item, "keyword", "keywordName", "keyword_name"),
            "vr": _normalize_innolitics_vr(
                _first_text(
                    item,
                    "vr",
                    "VR",
                    "valueRepresentation",
                    "value_representations",
                )
            ),
            "vm": _first_text(item, "vm", "VM", "valueMultiplicity"),
            "retired": _retired_value(item),
        }
        previous = elements.get(tag)
        candidate_score = _populated_field_count(candidate)
        previous_score = _populated_field_count(previous) if previous else -1
        if previous is None or candidate_score > previous_score:
            elements[tag] = candidate
    return elements


def _load_pydicom_data_elements() -> dict[str, dict[str, object]]:
    datadict = pytest.importorskip(
        "pydicom.datadict",
        reason="install pydicom to run pydicom dictionary differential checks",
    )
    dictionary = cast(dict[object, object], datadict.DicomDictionary)
    elements: dict[str, dict[str, object]] = {}
    for raw_tag, raw_record in dictionary.items():
        tag = _pydicom_tag(raw_tag)
        if tag is None:
            continue
        record = _pydicom_record(raw_record)
        if record is None:
            continue
        elements[tag] = record
    return elements


def _load_innolitics_ct_modules(path: Path) -> set[str]:
    finalized_modules = _load_finalized_innolitics_ct_modules(path)
    if finalized_modules:
        return finalized_modules

    for item in _walk_json_files(path):
        name = _first_text(item, "name", "Name", "title", "id")
        if name is None or _normalize_module_name(name) != "CT Image":
            continue
        modules = _first_sequence(item, "modules", "iodModules", "moduleTable")
        if modules is None:
            continue
        parsed = {
            _normalize_module_name(module_name)
            for module_name in (_module_name(module) for module in modules)
            if module_name is not None
        }
        if parsed:
            return parsed
    return set()


def _load_finalized_innolitics_ct_modules(path: Path) -> set[str]:
    if not path.is_dir():
        return set()
    ciods = _load_json_list(path / "ciods.json")
    relationships = _load_json_list(path / "ciod_to_modules.json")
    modules = _load_json_list(path / "modules.json")
    if not ciods or not relationships or not modules:
        return set()

    ct_iod = next(
        (
            item
            for item in ciods
            if _normalize_module_name(str(item.get("name", ""))) == "CT Image"
        ),
        None,
    )
    if ct_iod is None:
        return set()
    ct_iod_id = ct_iod.get("id")
    modules_by_id = {
        item.get("id"): _normalize_module_name(str(item.get("name", "")))
        for item in modules
        if item.get("id") is not None and item.get("name") is not None
    }
    return {
        module_name
        for relationship in relationships
        if relationship.get("ciodId") == ct_iod_id
        for module_name in [modules_by_id.get(relationship.get("moduleId"))]
        if module_name
    }


def _local_data_elements(
    connection: sqlite3.Connection, *, edition: str
) -> dict[str, dict[str, object]]:
    rows = connection.execute(
        """
        SELECT tag, name, keyword, vr, vm, retired
        FROM data_element
        WHERE edition_id = ?
          AND is_range = 0
        """,
        (edition,),
    )
    return {
        str(row["tag"]): {
            "name": row["name"],
            "keyword": row["keyword"],
            "vr": row["vr"],
            "vm": row["vm"],
            "retired": bool(row["retired"]),
        }
        for row in rows
    }


def _walk_json_files(path: Path) -> Iterator[dict[str, Any]]:
    paths = sorted(path.rglob("*.json")) if path.is_dir() else [path]
    for json_path in paths:
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            pytest.fail(f"invalid JSON in {json_path}: {exc}")
        yield from _walk_json(payload)


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _walk_json(value: object) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _load_allowlist() -> list[dict[str, object]]:
    payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    entries = payload.get("accepted_diffs", [])
    assert isinstance(entries, list)
    allowlist: list[dict[str, object]] = []
    for entry in entries:
        assert isinstance(entry, dict), "accepted differential entries must be objects"
        assert isinstance(entry.get("external"), str)
        assert isinstance(entry.get("entity_type"), str)
        assert isinstance(entry.get("id"), str)
        assert isinstance(entry.get("field"), str)
        assert entry.get("classification") in DIFF_CLASSIFICATIONS
        assert isinstance(entry.get("reason"), str) and entry["reason"]
        allowlist.append(entry)
    return allowlist


def _is_allowlisted(
    mismatch: dict[str, object], allowlist: list[dict[str, object]]
) -> bool:
    match_fields = ("external", "entity_type", "id", "field", "local", "external_value")
    return any(
        all(entry.get(field) == mismatch.get(field) for field in match_fields)
        for entry in allowlist
    )


def _first_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        normalized = _normalize_value(value)
        if normalized is not None:
            return normalized
    return None


def _first_sequence(item: dict[str, Any], *keys: str) -> list[object] | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, list):
            return value
    return None


def _normalize_value(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        values = [
            normalized
            for normalized in (_normalize_value(child) for child in value)
            if normalized is not None
        ]
        return " or ".join(values) if values else None
    text = str(value).strip()
    return text or None


def _retired_value(item: dict[str, Any]) -> bool | None:
    for key in ("retired", "isRetired", "retiredFlag"):
        if key not in item:
            continue
        value = item[key]
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "retired", "ret", "yes", "y"}
    return None


def _pydicom_tag(value: object) -> str | None:
    if isinstance(value, int):
        return f"({value >> 16:04X},{value & 0xFFFF:04X})"
    return None


def _pydicom_record(value: object) -> dict[str, object] | None:
    if not isinstance(value, tuple) or len(value) < 5:
        return None
    vr, vm, name, retired, keyword = value[:5]
    name_text = _normalize_pydicom_name(name)
    is_retired_blank = name_text == "Retired-blank"
    return {
        "name": "" if is_retired_blank else _strip_pydicom_retired_marker(name_text),
        "keyword": _normalize_value(keyword),
        "vr": None if is_retired_blank else _normalize_pydicom_vr(vr),
        "vm": None if is_retired_blank else _normalize_value(vm),
        "retired": _pydicom_retired_value(retired),
    }


def _normalize_pydicom_name(value: object) -> str | None:
    text = _normalize_value(value)
    if text is None:
        return None
    return text.replace(" uAs", " µAs").replace(" uS", " µS").replace(" uA", " µA")


def _strip_pydicom_retired_marker(value: str | None) -> str | None:
    return _strip_retired_parenthetical(value)


def _strip_retired_parenthetical(value: str | None) -> str | None:
    if value is None:
        return None
    return _normalize_value(value.replace(" (Retired)", ""))


def _normalize_innolitics_vr(value: str | None) -> str | None:
    if value == "See Note 2":
        return "See Note"
    return value


def _normalize_pydicom_vr(value: object) -> str | None:
    text = _normalize_value(value)
    if text == "NONE":
        return "See Note"
    return text


def _pydicom_retired_value(value: object) -> bool | None:
    text = _normalize_value(value)
    if text is None:
        return None
    return text.lower() == "retired"


def _populated_field_count(item: dict[str, object]) -> int:
    return sum(value is not None for value in item.values())


def _module_name(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return _first_text(value, "module", "moduleName", "name", "Name", "title")
    return None


def _normalize_module_name(value: str) -> str:
    text = value.strip()
    if text.lower().endswith(" module"):
        text = text[:-7]
    return " ".join(text.split())

"""Serialization helpers for IR records."""

from __future__ import annotations

from pydantic import BaseModel


def model_to_jsonable(model: BaseModel) -> dict[str, object]:
    """Return a JSON-compatible dictionary for a Pydantic model."""
    return model.model_dump(mode="json")

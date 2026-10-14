"""Public response contracts shared by CLI and future agent tools."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ResponseStatus = Literal["ok", "not_found", "validation_error"]


class StandardRef(BaseModel):
    """Where in the standard a fact comes from."""

    model_config = ConfigDict(frozen=True)

    part: str
    section: str | None = None
    table: str | None = None
    anchor: str | None = None
    edition: str
    # How the source line names it, when the id alone would read badly.
    label: str | None = None


class ToolResponse(BaseModel):
    """A resolver's answer: the result, its sources, and real gaps only."""

    model_config = ConfigDict(frozen=True)

    status: ResponseStatus
    result: dict[str, Any] | None
    refs: list[StandardRef] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def tool_response(
    *,
    status: ResponseStatus,
    result: dict[str, Any] | None,
    refs: list[StandardRef] | None = None,
    warnings: list[str] | None = None,
) -> ToolResponse:
    """Build a resolver response."""
    return ToolResponse(
        status=status,
        result=result,
        refs=refs or [],
        warnings=warnings or [],
    )

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ValidateNavigationDataProfileInput(BaseModel):
    profile: dict[str, Any]


class ValidateNavigationDataProfileOutput(BaseModel):
    ok: bool
    errors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)

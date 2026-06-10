from __future__ import annotations

from pydantic import BaseModel


class ListToolCapabilityCatalogInput(BaseModel):
    scenario: str | None = None
    stage_kind: str | None = None
    tool: str | None = None


class ListToolCapabilityCatalogOutput(BaseModel):
    ok: bool

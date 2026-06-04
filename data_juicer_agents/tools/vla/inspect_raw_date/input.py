from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_raw_root() -> str:
    return str(VLAPaths().raw_root)


class InspectRawDateInput(BaseModel):
    date: str
    raw_root: str = Field(default_factory=_default_raw_root)
    run_id: str | None = None
    log_dir: str | None = None


class InspectRawDateOutput(BaseModel):
    ok: bool

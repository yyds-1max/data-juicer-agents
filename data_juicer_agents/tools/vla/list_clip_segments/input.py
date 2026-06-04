from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_clip_root() -> str:
    return str(VLAPaths().clip_root)


class ListClipSegmentsInput(BaseModel):
    date: str
    clip_root: str = Field(default_factory=_default_clip_root)
    run_id: str | None = None
    log_dir: str | None = None


class ListClipSegmentsOutput(BaseModel):
    ok: bool

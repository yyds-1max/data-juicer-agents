from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_clip_root() -> str:
    return str(VLAPaths().clip_root)


def _default_finish_root() -> str:
    return str(VLAPaths().finish_root)


class InspectProcessingStateInput(BaseModel):
    date: str
    selected_segments: list[str] | None = None
    clip_root: str = Field(default_factory=_default_clip_root)
    finish_root: str = Field(default_factory=_default_finish_root)
    run_id: str | None = None
    log_dir: str | None = None

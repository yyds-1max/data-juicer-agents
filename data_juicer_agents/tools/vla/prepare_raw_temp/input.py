from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_clip_root() -> str:
    return str(VLAPaths().clip_root)


def _default_raw_root() -> str:
    return str(VLAPaths().raw_root)


class PrepareRawTempInput(BaseModel):
    date: str
    selected_segments: list[str]
    raw_root: str = Field(default_factory=_default_raw_root)
    clip_root: str = Field(default_factory=_default_clip_root)
    owner: str | None = None
    dry_run: bool = True
    run_id: str | None = None
    log_dir: str | None = None


class PrepareRawTempOutput(BaseModel):
    ok: bool

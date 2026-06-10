from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_clip_root() -> str:
    return str(VLAPaths().clip_root)


def _default_finish_root() -> str:
    return str(VLAPaths().finish_root)


class ValidateOutputsInput(BaseModel):
    date: str
    clip_root: str = Field(default_factory=_default_clip_root)
    finish_root: str = Field(default_factory=_default_finish_root)
    selected_segments: list[str]
    level: Literal["clip", "finish", "full"] = "full"
    expect_gridmap_output: bool | None = None
    run_id: str | None = None
    log_dir: str | None = None


class ValidateOutputsOutput(BaseModel):
    ok: bool

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_clip_root() -> str:
    return str(VLAPaths().clip_root)


def _default_finish_root() -> str:
    return str(VLAPaths().finish_root)


def _default_trajectory_root() -> str:
    return str(VLAPaths().trajectory_root)


class PrepareFinishDatasetInput(BaseModel):
    date: str
    selected_segments: list[str]
    scene_mode: Literal["in", "out"]
    clip_root: str = Field(default_factory=_default_clip_root)
    finish_root: str = Field(default_factory=_default_finish_root)
    trajectory_root: str = Field(default_factory=_default_trajectory_root)
    sensor_params_dir: str | None = None
    dry_run: bool = True
    run_id: str | None = None
    log_dir: str | None = None


class PrepareFinishDatasetOutput(BaseModel):
    ok: bool

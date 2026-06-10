from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths, VLARuntime


def _default_clip_root() -> str:
    return str(VLAPaths().clip_root)


def _default_finish_root() -> str:
    return str(VLAPaths().finish_root)


def _default_trajectory_root() -> str:
    return str(VLAPaths().trajectory_root)


def _default_data_env_setup() -> str | None:
    setup = VLARuntime().data_env_setup
    return str(setup) if setup else None


def _default_data_python() -> str:
    return VLARuntime().data_python


class PrepareGridmapInput(BaseModel):
    date: str
    selected_segments: list[str]
    clip_root: str = Field(default_factory=_default_clip_root)
    finish_root: str = Field(default_factory=_default_finish_root)
    trajectory_root: str = Field(default_factory=_default_trajectory_root)
    gridmap_variant: Literal["copy_existing_artifact", "pointcloud_to_gridmap"]
    data_env_setup: str | None = Field(default_factory=_default_data_env_setup)
    data_python: str = Field(default_factory=_default_data_python)
    generator_script: str | None = None
    timeout: int | None = Field(default=None, gt=0)
    dry_run: bool = True
    run_id: str | None = None
    log_dir: str | None = None


class PrepareGridmapOutput(BaseModel):
    ok: bool

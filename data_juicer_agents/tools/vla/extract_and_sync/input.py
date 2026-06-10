from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths, VLARuntime


def _default_raw_root() -> str:
    return str(VLAPaths().raw_root)


def _default_clip_root() -> str:
    return str(VLAPaths().clip_root)


def _default_data_toolbox_src() -> str:
    return str(VLAPaths().data_toolbox_src)


def _default_data_env_setup() -> str | None:
    setup = VLARuntime().data_env_setup
    return str(setup) if setup else None


def _default_data_python() -> str:
    return VLARuntime().data_python


class ExtractAndSyncInput(BaseModel):
    date: str
    selected_segments: list[str]
    raw_root: str = Field(default_factory=_default_raw_root)
    clip_root: str = Field(default_factory=_default_clip_root)
    data_toolbox_src: str = Field(default_factory=_default_data_toolbox_src)
    data_env_setup: str | None = Field(default_factory=_default_data_env_setup)
    data_python: str = Field(default_factory=_default_data_python)
    processes_num: int = Field(default=4, ge=1)
    query_dir: str = "lidar_points"
    sync_output_dir: str = "sync_data"
    sequence_suffix: str = "zhigu_wuhan"
    script_variant: Literal["u_legacy_topics", "go2w_current_topics"] = (
        "u_legacy_topics"
    )
    gt_dog_root: str | None = None
    extra_env: dict[str, str] = Field(default_factory=dict)
    dry_run: bool = False
    run_id: str | None = None
    log_dir: str | None = None


class ExtractAndSyncOutput(BaseModel):
    ok: bool

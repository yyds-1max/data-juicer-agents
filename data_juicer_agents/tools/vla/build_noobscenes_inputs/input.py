from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths, VLARuntime


def _default_trajectory_root() -> str:
    return str(VLAPaths().trajectory_root)


def _default_data_env_setup() -> str | None:
    setup = VLARuntime().data_env_setup
    return str(setup) if setup else None


def _default_data_python() -> str:
    return VLARuntime().data_python


class BuildNoobScenesInputsInput(BaseModel):
    save_path_temp: str
    trajectory_root: str = Field(default_factory=_default_trajectory_root)
    data_env_setup: str | None = Field(default_factory=_default_data_env_setup)
    data_python: str = Field(default_factory=_default_data_python)
    dataset_version: str = "v1.0-develop"
    dry_run: bool = True
    run_id: str | None = None
    log_dir: str | None = None


class BuildNoobScenesInputsOutput(BaseModel):
    ok: bool

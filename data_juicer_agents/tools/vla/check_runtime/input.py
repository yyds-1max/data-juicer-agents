from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLARuntime


def _default_data_env_setup() -> str | None:
    setup = VLARuntime().data_env_setup
    return str(setup) if setup else None


def _default_data_python() -> str:
    return VLARuntime().data_python


class CheckRuntimeInput(BaseModel):
    data_env_setup: str | None = Field(default_factory=_default_data_env_setup)
    data_python: str = Field(default_factory=_default_data_python)
    expected_data_python_major_minor: str = Field(default="3.8")
    dry_run: bool = False
    run_id: str | None = None
    log_dir: str | None = None


class CheckRuntimeOutput(BaseModel):
    ok: bool

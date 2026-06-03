from __future__ import annotations

from pydantic import BaseModel, Field


class CheckRuntimeInput(BaseModel):
    data_env_setup: str | None = None
    data_python: str = "python3"
    expected_data_python_major_minor: str = Field(default="3.8")
    dry_run: bool = False
    run_id: str | None = None
    log_dir: str | None = None


class CheckRuntimeOutput(BaseModel):
    ok: bool

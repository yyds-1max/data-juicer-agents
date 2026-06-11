from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RunWorkflowInput(BaseModel):
    scenario: Literal["navigation_vla"] = "navigation_vla"
    date: str
    segments: str | list[str] = "all"
    scene_mode: Literal["in", "out"] = "out"
    approve: bool = True
    dry_run: bool = False
    run_id: str | None = None
    agent_mode: Literal[
        "react",
        "deterministic",
        "react-with-deterministic-fallback",
    ] = "react"


class RunWorkflowOutput(BaseModel):
    ok: bool
    status: str
    run_id: str | None = None
    run_dir: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)

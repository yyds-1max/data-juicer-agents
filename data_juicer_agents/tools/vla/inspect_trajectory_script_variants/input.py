from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_trajectory_root() -> str:
    return str(VLAPaths().trajectory_root)


class InspectTrajectoryScriptVariantsInput(BaseModel):
    trajectory_root: str = Field(default_factory=_default_trajectory_root)
    run_id: str | None = None
    log_dir: str | None = None

from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_trajectory_root() -> str:
    return str(VLAPaths().trajectory_root)


class InspectCalibrationAssetsInput(BaseModel):
    trajectory_root: str = Field(default_factory=_default_trajectory_root)
    topic_schema: str
    run_id: str | None = None
    log_dir: str | None = None

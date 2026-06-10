from __future__ import annotations

from pydantic import BaseModel, Field

from data_juicer_agents.tools.vla._shared.config import VLAPaths


def _default_data_toolbox_src() -> str:
    return str(VLAPaths().data_toolbox_src)


class InspectDataToolboxVariantsInput(BaseModel):
    data_toolbox_src: str = Field(default_factory=_default_data_toolbox_src)
    run_id: str | None = None
    log_dir: str | None = None

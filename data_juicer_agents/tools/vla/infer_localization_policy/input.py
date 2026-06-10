from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class InferLocalizationPolicyInput(BaseModel):
    topics: list[dict[str, Any]]
    scene_mode: str = "unknown"
    requires_generated_ins: bool = False
    run_id: str | None = None
    log_dir: str | None = None

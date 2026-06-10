from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class InferSyncPolicyInput(BaseModel):
    topic_schema: str
    topics: list[dict[str, Any]]
    topic_mapping_variant: str = ""
    run_id: str | None = None
    log_dir: str | None = None

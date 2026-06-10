from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ClassifyNavigationTopicSchemaInput(BaseModel):
    topics: list[dict[str, Any]]
    date: str | None = None
    run_id: str | None = None
    log_dir: str | None = None

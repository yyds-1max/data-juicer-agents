from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlanAgentMemory(BaseModel):
    scenario: str | None = None
    user_inputs: dict[str, Any] = Field(default_factory=dict)
    source_docs: list[str] = Field(default_factory=list)
    planning_notes: dict[str, Any] = Field(default_factory=dict)
    pending_observations: list[str] = Field(default_factory=list)
    observations: list[dict[str, Any]] = Field(default_factory=list)
    profile_draft: dict[str, Any] = Field(default_factory=dict)
    data_profile_draft: dict[str, Any] = Field(default_factory=dict)
    plan_draft: dict[str, Any] = Field(default_factory=dict)
    profile_validation_feedback: dict[str, Any] = Field(default_factory=dict)
    plan_validation_feedback: dict[str, Any] = Field(default_factory=dict)
    current_phase: str | None = None
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    ready_to_plan: bool = False


__all__ = ["PlanAgentMemory"]

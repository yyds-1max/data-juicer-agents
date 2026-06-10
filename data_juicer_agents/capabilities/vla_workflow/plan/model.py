from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PlanScenario = Literal["navigation_vla", "manipulation_vla"]
PlanStatus = Literal["pending", "confirmed", "running", "completed", "failed"]
StageEffect = Literal["read", "write", "execute", "external"]
StageStatus = Literal["pending", "running", "success", "failed", "skipped"]


class VLAWorkflowStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    stage_kind: str
    tool: str
    variant: str
    effects: StageEffect
    decision_ref: str | None = None
    status: StageStatus = "pending"


class SkippedStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_kind: str
    reason: str
    evidence: list[str] = Field(default_factory=list)
    source: str = ""


class VLAWorkflowPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    scenario: PlanScenario
    status: PlanStatus
    planning_notes_ref: str
    observations_ref: str
    data_profile_ref: str
    active_stages: list[VLAWorkflowStage]
    skipped_stages: list[SkippedStage] = Field(default_factory=list)
    approval_required: bool = True


__all__ = [
    "PlanScenario",
    "PlanStatus",
    "SkippedStage",
    "StageEffect",
    "StageStatus",
    "VLAWorkflowPlan",
    "VLAWorkflowStage",
]

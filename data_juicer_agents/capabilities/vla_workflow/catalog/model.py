from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CapabilityStatus = Literal["available", "planned", "placeholder", "deprecated"]
ToolEffect = Literal["read", "write", "execute", "external"]


class ExpectedArtifact(BaseModel):
    kind: str
    path_template: str
    required: bool = True
    description: str = ""


class ToolVariant(BaseModel):
    id: str
    status: CapabilityStatus
    selectors: dict[str, list[str]] = Field(default_factory=dict)
    arg_bindings: dict[str, str] = Field(default_factory=dict)
    preconditions: list[dict[str, Any]] = Field(default_factory=list)
    expected_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    recoverable_errors: list[dict[str, Any]] = Field(default_factory=list)
    stage_config: dict[str, Any] = Field(default_factory=dict)


class ToolCapability(BaseModel):
    tool: str
    scenario: str
    stage_kind: str
    effects: ToolEffect
    implementation_status: CapabilityStatus
    supports_dry_run: bool
    plan_agent_allowed: bool
    executor_agent_allowed: bool
    variants: list[ToolVariant] = Field(default_factory=list)


__all__ = [
    "CapabilityStatus",
    "ExpectedArtifact",
    "ToolEffect",
    "ToolCapability",
    "ToolVariant",
]

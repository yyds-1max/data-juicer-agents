from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InferSyncPolicyInput
from .logic import infer_sync_policy


def _infer_sync_policy(_ctx: ToolContext, args: InferSyncPolicyInput) -> ToolResult:
    payload = infer_sync_policy(**args.model_dump())
    if payload.get("ok"):
        return ToolResult.success(summary="inferred navigation sync policy", data=payload)
    return ToolResult.failure(
        summary="failed to infer navigation sync policy",
        error_type=str(payload["blocking_issues"][0]["type"]),
        data=payload,
    )


VLA_INFER_SYNC_POLICY = ToolSpec(
    name="vla_infer_sync_policy",
    description="Infer navigation sync query directory from topic schema and mapping facts.",
    input_model=InferSyncPolicyInput,
    output_model=None,
    executor=_infer_sync_policy,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InferLocalizationPolicyInput
from .logic import infer_localization_policy


def _infer_localization_policy(_ctx: ToolContext, args: InferLocalizationPolicyInput) -> ToolResult:
    payload = infer_localization_policy(**args.model_dump())
    if payload.get("ok"):
        return ToolResult.success(summary="inferred navigation localization policy", data=payload)
    return ToolResult.failure(
        summary="missing navigation localization source",
        error_type=str(payload["blocking_issues"][0]["type"]),
        data=payload,
    )


VLA_INFER_LOCALIZATION_POLICY = ToolSpec(
    name="vla_infer_localization_policy",
    description="Infer localization source and NoobScenes input variant from raw topics.",
    input_model=InferLocalizationPolicyInput,
    output_model=None,
    executor=_infer_localization_policy,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

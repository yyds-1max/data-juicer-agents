from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ValidateOutputsInput, ValidateOutputsOutput
from .logic import validate_outputs


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: ValidateOutputsInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / args.date / run_id
        )
    return payload


def _validate_outputs(ctx: ToolContext, args: ValidateOutputsInput) -> ToolResult:
    payload = validate_outputs(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        return ToolResult.success(
            summary=f"VLA {payload.get('level')} outputs are ready",
            data=payload,
        )
    return ToolResult.failure(
        summary=f"VLA {payload.get('level')} outputs are incomplete",
        error_type="vla_outputs_incomplete",
        data=payload,
        next_actions=[
            f"Run next suggested VLA stage: {payload.get('suggested_next_action')}."
        ],
    )


VLA_VALIDATE_OUTPUTS = ToolSpec(
    name="vla_validate_outputs",
    description="Validate VLA clip, finish, annotation, tracking, projection, and trajectory outputs.",
    input_model=ValidateOutputsInput,
    output_model=ValidateOutputsOutput,
    executor=_validate_outputs,
    tags=("vla", "read"),
    effects="read",
    confirmation="none",
)


__all__ = ["VLA_VALIDATE_OUTPUTS"]

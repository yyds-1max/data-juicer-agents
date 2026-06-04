from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import RunTrackingInput, RunTrackingOutput
from .logic import run_tracking


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: RunTrackingInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / "tracking" / run_id
        )
    return payload


def _run_tracking(ctx: ToolContext, args: RunTrackingInput) -> ToolResult:
    payload = run_tracking(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        action = "planned" if payload.get("dry_run") else "completed"
        return ToolResult.success(
            summary=f"{action} VLA tracking for {payload.get('yaml_count', 0)} YAML files",
            data=payload,
        )
    return ToolResult.failure(
        summary=str(payload.get("message", "VLA tracking failed")),
        error_type=str(payload.get("error_type", "tracking_failed")),
        data=payload,
        next_actions=[
            "Inspect failed YAML paths and tracking stdout/stderr, then rerun tracking for corrected annotations."
        ],
    )


VLA_RUN_TRACKING = ToolSpec(
    name="vla_run_tracking",
    description="Run or dry-run the VLA ONNX tracking binary once for each annotation YAML.",
    input_model=RunTrackingInput,
    output_model=RunTrackingOutput,
    executor=_run_tracking,
    tags=("vla", "execute"),
    effects="execute",
    confirmation="required",
)


__all__ = ["VLA_RUN_TRACKING"]

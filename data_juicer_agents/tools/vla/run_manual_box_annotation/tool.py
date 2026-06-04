from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import RunManualBoxAnnotationInput, RunManualBoxAnnotationOutput
from .logic import run_manual_box_annotation


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: RunManualBoxAnnotationInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / "annotation" / run_id
        )
    return payload


def _run_manual_box_annotation(
    ctx: ToolContext, args: RunManualBoxAnnotationInput
) -> ToolResult:
    payload = run_manual_box_annotation(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        action = "planned" if payload.get("dry_run") else "completed"
        return ToolResult.success(
            summary=f"{action} VLA manual annotation checkpoint",
            data=payload,
        )
    return ToolResult.failure(
        summary=str(
            payload.get("checkpoint_message", "VLA manual annotation checkpoint failed")
        ),
        error_type=str(payload.get("error_type", "manual_annotation_failed")),
        data=payload,
        next_actions=[
            "Retry gen_box.py in a GUI-capable runtime, skip clips with missing YAML, or stop the VLA run."
        ],
    )


VLA_RUN_MANUAL_BOX_ANNOTATION = ToolSpec(
    name="vla_run_manual_box_annotation",
    description=(
        "Launch gen_box.py as a human-in-the-loop VLA annotation checkpoint "
        "and inspect generated YAML files."
    ),
    input_model=RunManualBoxAnnotationInput,
    output_model=RunManualBoxAnnotationOutput,
    executor=_run_manual_box_annotation,
    tags=("vla", "execute"),
    effects="execute",
    confirmation="required",
)


__all__ = ["VLA_RUN_MANUAL_BOX_ANNOTATION"]

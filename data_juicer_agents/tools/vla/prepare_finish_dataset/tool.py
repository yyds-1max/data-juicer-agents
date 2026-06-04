from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import PrepareFinishDatasetInput, PrepareFinishDatasetOutput
from .logic import prepare_finish_dataset


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: PrepareFinishDatasetInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / args.date / run_id
        )
    return payload


def _prepare_finish_dataset(
    ctx: ToolContext, args: PrepareFinishDatasetInput
) -> ToolResult:
    payload = prepare_finish_dataset(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        action = "planned" if payload.get("dry_run") else "prepared"
        return ToolResult.success(
            summary=f"{action} finish dataset for {payload.get('clip_count', 0)} VLA clips",
            data=payload,
        )
    return ToolResult.failure(
        summary="VLA finish dataset preparation failed",
        error_type=str(payload.get("error_type", "prepare_finish_dataset_failed")),
        data=payload,
        next_actions=[
            "Run vla_list_clip_segments and select segments that contain sync_data."
        ],
    )


VLA_PREPARE_FINISH_DATASET = ToolSpec(
    name="vla_prepare_finish_dataset",
    description="Copy or dry-run selected sync_data clips into finish_data/DATE_temp samples.",
    input_model=PrepareFinishDatasetInput,
    output_model=PrepareFinishDatasetOutput,
    executor=_prepare_finish_dataset,
    tags=("vla", "write"),
    effects="write",
    confirmation="required",
)


__all__ = ["VLA_PREPARE_FINISH_DATASET"]

from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import PrepareGridmapInput, PrepareGridmapOutput
from .logic import prepare_gridmap


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: PrepareGridmapInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / args.date / "gridmap" / run_id
        )
    return payload


def _prepare_gridmap(ctx: ToolContext, args: PrepareGridmapInput) -> ToolResult:
    payload = prepare_gridmap(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        action = "planned" if payload.get("dry_run") else "prepared"
        return ToolResult.success(
            summary=(
                f"{action} {payload.get('prepared_gridmap_count', 0)} "
                "VLA grid_map artifacts"
            ),
            data=payload,
        )
    return ToolResult.failure(
        summary="VLA gridmap preparation failed",
        error_type=str(payload.get("error_type", "prepare_gridmap_failed")),
        data=payload,
        next_actions=[
            "Inspect clip_data sync_data grid_map artifacts or run pointcloud_to_gridmap."
        ],
    )


VLA_PREPARE_GRIDMAP = ToolSpec(
    name="vla_prepare_gridmap",
    description=(
        "Prepare required VLA grid_map artifacts by copying existing clip artifacts "
        "or generating them from synchronized pointcloud PCD files."
    ),
    input_model=PrepareGridmapInput,
    output_model=PrepareGridmapOutput,
    executor=_prepare_gridmap,
    tags=("vla", "execute"),
    effects="execute",
    confirmation="required",
)


__all__ = ["VLA_PREPARE_GRIDMAP"]

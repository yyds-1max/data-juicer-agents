from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ExtractAndSyncInput, ExtractAndSyncOutput
from .logic import extract_and_sync


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: ExtractAndSyncInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / args.date / run_id
        )
    return payload


def _extract_and_sync(ctx: ToolContext, args: ExtractAndSyncInput) -> ToolResult:
    payload = extract_and_sync(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        action = "planned" if payload.get("dry_run") else "processed"
        return ToolResult.success(
            summary=f"{action} extract and sync for {len(payload.get('segments', []))} VLA segments",
            data=payload,
        )
    return ToolResult.failure(
        summary="VLA extract and sync failed",
        error_type=str(payload.get("error_type", "extract_sync_failed")),
        data=payload,
        next_actions=[
            "Inspect the failed segment command stdout/stderr, then rerun this tool for the remaining segments.",
        ],
    )


VLA_EXTRACT_AND_SYNC = ToolSpec(
    name="vla_extract_and_sync",
    description="Run or dry-run run_U-style VLA ROS2 extraction and timestamp synchronization per segment.",
    input_model=ExtractAndSyncInput,
    output_model=ExtractAndSyncOutput,
    executor=_extract_and_sync,
    tags=("vla", "execute"),
    effects="execute",
    confirmation="required",
)


__all__ = ["VLA_EXTRACT_AND_SYNC"]

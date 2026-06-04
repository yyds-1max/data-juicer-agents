from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ListClipSegmentsInput, ListClipSegmentsOutput
from .logic import list_clip_segments


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: ListClipSegmentsInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / args.date / run_id
        )
    return payload


def _list_clip_segments(ctx: ToolContext, args: ListClipSegmentsInput) -> ToolResult:
    payload = list_clip_segments(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        return ToolResult.success(
            summary=f"found {payload.get('count', 0)} VLA clip segments",
            data=payload,
        )
    return ToolResult.failure(
        summary="clip date directory is missing",
        error_type=str(payload.get("error_type", "missing_clip_date")),
        data=payload,
        next_actions=["Run vla_extract_and_sync first, or check clip_root/date."],
    )


VLA_LIST_CLIP_SEGMENTS = ToolSpec(
    name="vla_list_clip_segments",
    description="List clip_data/DATE segment folders and report which contain sync_data.",
    input_model=ListClipSegmentsInput,
    output_model=ListClipSegmentsOutput,
    executor=_list_clip_segments,
    tags=("vla", "read"),
    effects="read",
    confirmation="none",
)


__all__ = ["VLA_LIST_CLIP_SEGMENTS"]

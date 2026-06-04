from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InspectRawDateInput, InspectRawDateOutput
from .logic import inspect_raw_date


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: InspectRawDateInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(ctx.resolve_artifacts_dir() / "vla_runs" / args.date / run_id)
    return payload


def _inspect_raw_date(ctx: ToolContext, args: InspectRawDateInput) -> ToolResult:
    payload = inspect_raw_date(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        return ToolResult.success(
            summary=f"found {payload.get('count', 0)} raw VLA segments",
            data=payload,
        )
    return ToolResult.failure(
        summary="raw date directory is missing",
        error_type=str(payload.get("error_type", "missing_raw_date")),
        data=payload,
        next_actions=["Check raw_root/date or run the server-side data copy first."],
    )


VLA_INSPECT_RAW_DATE = ToolSpec(
    name="vla_inspect_raw_date",
    description="List raw ROS2 db3 segment folders for a VLA processing date.",
    input_model=InspectRawDateInput,
    output_model=InspectRawDateOutput,
    executor=_inspect_raw_date,
    tags=("vla", "read"),
    effects="read",
    confirmation="none",
)


__all__ = ["VLA_INSPECT_RAW_DATE"]

from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import PrepareRawTempInput, PrepareRawTempOutput
from .logic import prepare_raw_temp


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: PrepareRawTempInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(ctx.resolve_artifacts_dir() / "vla_runs" / args.date / run_id)
    return payload


def _prepare_raw_temp(ctx: ToolContext, args: PrepareRawTempInput) -> ToolResult:
    payload = prepare_raw_temp(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        action = "planned" if payload.get("dry_run") else "prepared"
        return ToolResult.success(
            summary=f"{action} {len(payload.get('links', []))} raw VLA temp links",
            data=payload,
        )
    return ToolResult.failure(
        summary="raw VLA temp preparation failed",
        error_type=str(payload.get("error_type", "prepare_raw_temp_failed")),
        data=payload,
        next_actions=["Inspect available folders with vla_inspect_raw_date and select existing segments."],
    )


VLA_PREPARE_RAW_TEMP = ToolSpec(
    name="vla_prepare_raw_temp",
    description=(
        "Create or dry-run raw_data/DATE_temp symlinks and clip_data/DATE "
        "for selected VLA raw db3 segment folders."
    ),
    input_model=PrepareRawTempInput,
    output_model=PrepareRawTempOutput,
    executor=_prepare_raw_temp,
    tags=("vla", "write"),
    effects="write",
    confirmation="required",
)


__all__ = ["VLA_PREPARE_RAW_TEMP"]

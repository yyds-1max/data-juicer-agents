from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import CheckRuntimeInput, CheckRuntimeOutput
from .logic import check_runtime


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: CheckRuntimeInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / "runtime" / run_id
        )
    return payload


def _check_runtime(ctx: ToolContext, args: CheckRuntimeInput) -> ToolResult:
    payload = check_runtime(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        return ToolResult.success(
            summary=str(payload.get("message", "VLA runtime check passed")),
            data=payload,
        )
    return ToolResult.failure(
        summary=str(payload.get("message", "VLA runtime check failed")),
        error_type="vla_runtime_mismatch",
        data=payload,
        next_actions=[
            "Set AGENT_DATA_PYTHON to an absolute Python 3.8 executable "
            "and rerun vla_check_runtime."
        ],
    )


VLA_CHECK_RUNTIME = ToolSpec(
    name="vla_check_runtime",
    description=(
        "Verify that the Agent runtime is isolated from the legacy Python 3.8 "
        "data-processing runtime."
    ),
    input_model=CheckRuntimeInput,
    output_model=CheckRuntimeOutput,
    executor=_check_runtime,
    tags=("vla", "process", "read"),
    effects="read",
    confirmation="none",
)


__all__ = ["VLA_CHECK_RUNTIME"]

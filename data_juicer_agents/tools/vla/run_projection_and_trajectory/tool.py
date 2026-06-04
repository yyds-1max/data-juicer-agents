from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import RunProjectionTrajectoryInput, RunProjectionTrajectoryOutput
from .logic import run_projection_and_trajectory


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: RunProjectionTrajectoryInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / "projection" / run_id
        )
    return payload


def _run_projection_and_trajectory(
    ctx: ToolContext, args: RunProjectionTrajectoryInput
) -> ToolResult:
    payload = run_projection_and_trajectory(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        action = "planned" if payload.get("dry_run") else "completed"
        return ToolResult.success(
            summary=f"{action} VLA projection and trajectory with {len(payload.get('steps', []))} steps",
            data=payload,
        )
    return ToolResult.failure(
        summary="VLA projection and trajectory failed",
        error_type=str(
            payload.get("error_type", "run_projection_and_trajectory_failed")
        ),
        data=payload,
        next_actions=[
            "Inspect projection command stdout/stderr, then rerun from vla_run_projection_and_trajectory."
        ],
    )


VLA_RUN_PROJECTION_AND_TRAJECTORY = ToolSpec(
    name="vla_run_projection_and_trajectory",
    description="Run or dry-run VLA point projection, world conversion, trajectory generation, and result movement.",
    input_model=RunProjectionTrajectoryInput,
    output_model=RunProjectionTrajectoryOutput,
    executor=_run_projection_and_trajectory,
    tags=("vla", "execute"),
    effects="execute",
    confirmation="required",
)


__all__ = ["VLA_RUN_PROJECTION_AND_TRAJECTORY"]

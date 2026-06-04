from __future__ import annotations

from datetime import datetime, timezone

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import BuildNoobScenesInputsInput, BuildNoobScenesInputsOutput
from .logic import build_noobscenes_inputs


def _default_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"run_{stamp}"


def _with_default_logging(ctx: ToolContext, args: BuildNoobScenesInputsInput) -> dict:
    payload = args.model_dump()
    run_id = args.run_id or _default_run_id()
    payload["run_id"] = run_id
    if not args.log_dir:
        payload["log_dir"] = str(
            ctx.resolve_artifacts_dir() / "vla_runs" / "noobscenes" / run_id
        )
    return payload


def _build_noobscenes_inputs(
    ctx: ToolContext, args: BuildNoobScenesInputsInput
) -> ToolResult:
    payload = build_noobscenes_inputs(**_with_default_logging(ctx, args))
    if payload.get("ok"):
        action = "planned" if payload.get("dry_run") else "built"
        return ToolResult.success(
            summary=f"{action} NoobScenes inputs with {len(payload.get('commands', []))} commands",
            data=payload,
        )
    return ToolResult.failure(
        summary="NoobScenes input preparation failed",
        error_type=str(payload.get("error_type", "build_noobscenes_inputs_failed")),
        data=payload,
        next_actions=[
            "Inspect command stdout/stderr and rerun after fixing the data runtime or missing files."
        ],
    )


VLA_BUILD_NOOBSCENES_INPUTS = ToolSpec(
    name="vla_build_noobscenes_inputs",
    description="Run or dry-run deterministic NoobScenes preprocessing before manual annotation.",
    input_model=BuildNoobScenesInputsInput,
    output_model=BuildNoobScenesInputsOutput,
    executor=_build_noobscenes_inputs,
    tags=("vla", "execute"),
    effects="execute",
    confirmation="required",
)


__all__ = ["VLA_BUILD_NOOBSCENES_INPUTS"]

from __future__ import annotations

from typing import Callable

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import RunWorkflowInput, RunWorkflowOutput


def _progress_callback(ctx: ToolContext) -> Callable[..., None] | None:
    callback = ctx.runtime_values.get("emit_event")
    return callback if callable(callback) else None


def _run_workflow(ctx: ToolContext, args: RunWorkflowInput) -> ToolResult:
    from data_juicer_agents.capabilities.vla_workflow.service import execute_vla_workflow

    result = execute_vla_workflow(
        args,
        tool_context=ctx,
        progress_callback=_progress_callback(ctx),
    )
    payload = result.payload
    summary = str(payload.get("user_message") or payload.get("message") or "")
    if payload.get("ok"):
        return ToolResult.success(summary=summary, data=payload)
    return ToolResult.failure(
        summary=summary or "VLA workflow failed",
        error_type=str(payload.get("error_type") or "vla_workflow_failed"),
        data=payload,
        next_actions=["Inspect the workflow run directory and retry the failed or paused stage."],
    )


VLA_RUN_WORKFLOW = ToolSpec(
    name="vla_run_workflow",
    description=(
        "Run the structured navigation VLA workflow for complex VLA data "
        "processing requests. Prefer this tool over manually chaining atomic "
        "VLA tools: it invokes the Plan-Agent to create planning artifacts, "
        "then the Executor-Agent stage loop, and emits progress events. Call "
        "this tool exactly once with parsed date, segments, scene_mode, "
        "approve, and dry_run. Ordinary 'process data' requests should use "
        "approve=true and dry_run=false; use dry_run=true only when the user "
        "explicitly asks for preview/rehearsal/no execution. By default the "
        "workflow uses real Plan-Agent and Executor-Agent ReAct agents. Use "
        "agent_mode=deterministic or agent_mode=react-with-deterministic-fallback "
        "only when explicitly requested; fallback is reported visibly."
    ),
    input_model=RunWorkflowInput,
    output_model=RunWorkflowOutput,
    executor=_run_workflow,
    tags=("vla", "workflow", "execute"),
    effects="execute",
    confirmation="required",
)


__all__ = ["VLA_RUN_WORKFLOW"]

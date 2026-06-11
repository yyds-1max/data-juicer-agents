# -*- coding: utf-8 -*-
"""Reusable VLA workflow runner for CLI and session tools."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from data_juicer_agents.capabilities.vla_workflow.graph import (
    VLAWorkflowState,
    ask_confirmation,
    executor_agent_execute_stage,
    final_summary,
    generate_workflow_plan,
    initialize_state,
    plan_agent_fill_data_profile,
    plan_agent_inspect_loop,
    plan_agent_read_docs,
    route_after_stage,
    save_observations,
    save_planning_notes,
    select_next_stage,
    update_state,
    validate_data_profile,
    validate_plan_node,
)
from data_juicer_agents.capabilities.vla_workflow.persistence import (
    DATA_PROFILE_FILE,
    OBSERVATIONS_FILE,
    PLAN_FILE,
    PLANNING_NOTES_FILE,
    save_workflow_plan,
)
from data_juicer_agents.capabilities.vla_workflow.plan_agent import build_observation
from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.tools.vla._shared.config import VLAPaths
from data_juicer_agents.tools.vla.classify_navigation_topic_schema.logic import (
    classify_navigation_topic_schema,
)
from data_juicer_agents.tools.vla.infer_localization_policy.logic import (
    infer_localization_policy,
)
from data_juicer_agents.tools.vla.infer_sync_policy.logic import infer_sync_policy
from data_juicer_agents.tools.vla.inspect_calibration_assets.logic import (
    inspect_calibration_assets,
)
from data_juicer_agents.tools.vla.inspect_gridmap_artifacts.logic import (
    inspect_gridmap_artifacts,
)
from data_juicer_agents.tools.vla.inspect_processing_state.logic import (
    inspect_processing_state,
)
from data_juicer_agents.tools.vla.inspect_raw_layout.logic import inspect_raw_layout
from data_juicer_agents.tools.vla.inspect_rosbag_metadata.logic import (
    inspect_rosbag_metadata,
)

STAGE_RESULTS_FILE = "stage_results.json"
AGENT_MODE_REACT = "react"
AGENT_MODE_DETERMINISTIC = "deterministic"
AGENT_MODE_REACT_WITH_FALLBACK = "react-with-deterministic-fallback"


@dataclass(frozen=True)
class VLAWorkflowRunResult:
    exit_code: int
    payload: dict[str, Any]


def _get_param(params: Any, name: str, default: Any = None) -> Any:
    if isinstance(params, dict):
        return params.get(name, default)
    return getattr(params, name, default)


def _segments_arg(value: str | list[str] | None) -> str | list[str]:
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or "all"
    raw = str(value or "all").strip()
    if not raw or raw.lower() == "all":
        return "all"
    return [item.strip() for item in raw.split(",") if item.strip()]


def _segments_for_tools(value: str | list[str]) -> list[str]:
    if value == "all":
        return []
    return list(value)


def _default_tool_context() -> ToolContext:
    root = str(Path("./.djx").expanduser())
    return ToolContext(working_dir=root, artifacts_dir=root)


def _first_segment(raw_layout: dict[str, Any], selected_segments: list[str]) -> str | None:
    available = [str(item.get("name") or "") for item in raw_layout.get("segments", [])]
    available = [item for item in available if item]
    if selected_segments:
        for item in selected_segments:
            if item in available:
                return item
    return available[0] if available else None


def _navigation_observations(
    *,
    user_inputs: dict[str, Any],
    paths: VLAPaths,
    run_id: str,
    log_dir: str,
) -> list[dict[str, Any]]:
    date = str(user_inputs["date"])
    scene_mode = str(user_inputs["scene_mode"])
    selected_segments = _segments_for_tools(user_inputs["selected_segments"])
    raw_root = str(paths.raw_root)
    clip_root = str(paths.clip_root)
    finish_root = str(paths.finish_root)
    trajectory_root = str(paths.trajectory_root)

    raw_layout = inspect_raw_layout(
        date=date,
        raw_root=raw_root,
        selected_segments=selected_segments,
        run_id=run_id,
        log_dir=log_dir,
    )
    first_segment = _first_segment(raw_layout, selected_segments)
    metadata = inspect_rosbag_metadata(
        raw_root=raw_root,
        date=date,
        segment=first_segment,
        run_id=run_id,
        log_dir=log_dir,
    )
    topics = list(metadata.get("topics") or [])
    topic_schema = classify_navigation_topic_schema(
        topics=topics,
        date=date,
        run_id=run_id,
        log_dir=log_dir,
    )
    sync_policy = infer_sync_policy(
        topic_schema=str(topic_schema.get("topic_schema") or "unknown_topics"),
        topic_mapping_variant=str(topic_schema.get("topic_mapping_variant") or ""),
        topics=topics,
        run_id=run_id,
        log_dir=log_dir,
    )
    processing = inspect_processing_state(
        date=date,
        clip_root=clip_root,
        finish_root=finish_root,
        selected_segments=selected_segments,
        run_id=run_id,
        log_dir=log_dir,
    )
    localization = infer_localization_policy(
        topics=topics,
        scene_mode=scene_mode,
        run_id=run_id,
        log_dir=log_dir,
    )
    calibration = inspect_calibration_assets(
        trajectory_root=trajectory_root,
        topic_schema=str(topic_schema.get("topic_schema") or "unknown_topics"),
        run_id=run_id,
        log_dir=log_dir,
    )
    gridmap = inspect_gridmap_artifacts(
        date=date,
        clip_root=clip_root,
        finish_root=finish_root,
        topics=topics,
        selected_segments=selected_segments,
        run_id=run_id,
        log_dir=log_dir,
    )

    return [
        build_observation(
            observation_id="obs_raw_layout",
            tool="vla_inspect_raw_layout",
            raw_result=raw_layout,
        ),
        build_observation(
            observation_id="obs_metadata",
            tool="vla_inspect_rosbag_metadata",
            raw_result=metadata,
        ),
        build_observation(
            observation_id="obs_topic_schema",
            tool="vla_classify_navigation_topic_schema",
            raw_result=topic_schema,
        ),
        build_observation(
            observation_id="obs_sync",
            tool="vla_infer_sync_policy",
            raw_result=sync_policy,
        ),
        build_observation(
            observation_id="obs_processing",
            tool="vla_inspect_processing_state",
            raw_result=processing,
        ),
        build_observation(
            observation_id="obs_localization",
            tool="vla_infer_localization_policy",
            raw_result=localization,
        ),
        build_observation(
            observation_id="obs_calibration",
            tool="vla_inspect_calibration_assets",
            raw_result=calibration,
        ),
        build_observation(
            observation_id="obs_gridmap",
            tool="vla_inspect_gridmap_artifacts",
            raw_result=gridmap,
        ),
    ]


def _emit(
    progress_callback: Callable[..., None] | None,
    event_type: str,
    **payload: Any,
) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(event_type, **payload)
    except TypeError:
        event = {"type": event_type}
        event.update(payload)
        progress_callback(event)


def _planning_state(
    params: Any,
    *,
    tool_context: ToolContext | None,
    progress_callback: Callable[..., None] | None,
    agent_mode: str,
) -> VLAWorkflowState:
    scenario = str(_get_param(params, "scenario", "") or "navigation_vla").strip()
    selected_segments = _segments_arg(_get_param(params, "segments", None))
    user_inputs: dict[str, Any] = {
        "scenario": scenario,
        "date": str(_get_param(params, "date", "") or "").strip(),
        "selected_segments": selected_segments,
        "scene_mode": str(_get_param(params, "scene_mode", "") or "out").strip(),
    }
    paths = VLAPaths()
    user_inputs.update(
        {
            "raw_root": str(paths.raw_root),
            "clip_root": str(paths.clip_root),
            "finish_root": str(paths.finish_root),
            "trajectory_root": str(paths.trajectory_root),
        }
    )
    state = VLAWorkflowState(
        user_request=(
            f"Run {scenario} workflow for date {user_inputs['date']} "
            f"segments {_get_param(params, 'segments', 'all')}."
        ),
        scenario=scenario,
        user_inputs=user_inputs,
        run_id=str(_get_param(params, "run_id", "") or "").strip(),
        approval_status="approved" if _get_param(params, "approve", False) else "not_required",
    )
    state = initialize_state(state, tool_context=tool_context or _default_tool_context())
    state.runtime_context["requested_agent_mode"] = agent_mode
    state.runtime_context["agent_mode"] = (
        AGENT_MODE_DETERMINISTIC if agent_mode == AGENT_MODE_DETERMINISTIC else AGENT_MODE_REACT
    )
    state.runtime_context["fallback_used"] = False
    _emit(
        progress_callback,
        "vla_workflow_started",
        run_id=state.run_id,
        run_dir=state.run_dir,
        status=state.status,
        summary="Plan-Agent: 正在生成导航 VLA 处理计划",
    )
    _emit(
        progress_callback,
        "vla_plan_started",
        run_id=state.run_id,
        run_dir=state.run_dir,
        status=state.status,
        summary="Plan-Agent: 正在生成导航 VLA 处理计划",
    )

    if agent_mode != AGENT_MODE_DETERMINISTIC:
        return _react_planning_state(
            state,
            tool_context=tool_context or _default_tool_context(),
            progress_callback=progress_callback,
        )

    return _deterministic_planning_state(
        state,
        user_inputs=user_inputs,
        paths=paths,
        progress_callback=progress_callback,
    )


def _deterministic_planning_state(
    state: VLAWorkflowState,
    *,
    user_inputs: dict[str, Any],
    paths: VLAPaths,
    progress_callback: Callable[..., None] | None,
) -> VLAWorkflowState:
    if state.scenario == "navigation_vla":
        state.observations = _navigation_observations(
            user_inputs=user_inputs,
            paths=paths,
            run_id=state.run_id,
            log_dir=state.run_dir,
        )

    state = plan_agent_read_docs(state)
    state = save_planning_notes(state)
    state = plan_agent_inspect_loop(state)
    state = save_observations(state)
    state = plan_agent_fill_data_profile(state)
    state = validate_data_profile(state)
    if state.status == "failed":
        return state
    state = generate_workflow_plan(state)
    state = validate_plan_node(state)
    if state.status == "failed":
        return state
    state = ask_confirmation(state)
    _emit(
        progress_callback,
        "vla_plan_completed",
        run_id=state.run_id,
        run_dir=state.run_dir,
        status=state.status,
        summary=_plan_completed_summary(state),
        plan_id=state.plan.plan_id if state.plan is not None else None,
    )
    return state


def _react_planning_state(
    state: VLAWorkflowState,
    *,
    tool_context: ToolContext,
    progress_callback: Callable[..., None] | None,
) -> VLAWorkflowState:
    from data_juicer_agents.capabilities.vla_workflow.react_agents import (
        run_plan_agent_react,
    )

    state = plan_agent_read_docs(state)
    state = save_planning_notes(state)
    result = run_plan_agent_react(
        user_request=state.user_request,
        scenario=state.scenario or "navigation_vla",
        user_inputs=state.user_inputs,
        planning_notes=state.plan_agent_memory.planning_notes,
        source_docs=state.plan_agent_memory.source_docs,
        tool_context=tool_context,
        progress_callback=progress_callback,
    )
    state.plan_agent_memory = result["memory"]
    state.observations = list(result["observations"])
    state.data_profile = result["data_profile"]
    state.plan = result["plan"]
    state = save_observations(state)
    state = validate_data_profile(state)
    if state.status == "failed":
        return state
    state = generate_workflow_plan(state)
    state = validate_plan_node(state)
    if state.status == "failed":
        return state
    state = ask_confirmation(state)
    _emit(
        progress_callback,
        "vla_plan_completed",
        run_id=state.run_id,
        run_dir=state.run_dir,
        status=state.status,
        summary=_plan_completed_summary(state),
        plan_id=state.plan.plan_id if state.plan is not None else None,
    )
    return state


def _artifact_paths(state: VLAWorkflowState) -> dict[str, str]:
    run_dir = Path(state.run_dir).expanduser()
    return {
        "planning_notes": str(run_dir / PLANNING_NOTES_FILE),
        "observations": str(run_dir / OBSERVATIONS_FILE),
        "data_profile": str(run_dir / DATA_PROFILE_FILE),
        "plan": str(run_dir / PLAN_FILE),
        "stage_results": str(run_dir / STAGE_RESULTS_FILE),
    }


def _payload(state: VLAWorkflowState, *, dry_run: bool, exit_code: int) -> dict[str, Any]:
    plan = state.plan
    payload = {
        "ok": exit_code == 0,
        "action": "vla_workflow_run",
        "dry_run": bool(dry_run),
        "scenario": state.scenario,
        "date": state.user_inputs.get("date"),
        "run_id": state.run_id,
        "run_dir": state.run_dir,
        "status": state.status,
        "approval_status": state.approval_status,
        "approval_required": bool(plan.approval_required) if plan is not None else False,
        "plan_id": plan.plan_id if plan is not None else None,
        "active_stage_count": len(plan.active_stages) if plan is not None else 0,
        "stage_result_count": len(state.stage_results),
        "current_stage_id": state.current_stage_id,
        "artifacts": _artifact_paths(state),
        "messages": state.messages,
    }
    payload["progress_summary"] = _progress_summary(state)
    payload["user_message"] = _user_message(state)
    return payload


def _execution_context(state: VLAWorkflowState, *, dry_run: bool) -> dict[str, Any]:
    user_inputs = state.user_inputs
    date = str(user_inputs.get("date") or "").strip()
    finish_root = Path(str(user_inputs.get("finish_root") or VLAPaths().finish_root))
    save_path = str(finish_root / date)
    save_path_temp = str(finish_root / f"{date}_temp")

    context = dict(state.runtime_context)
    context["dry_run"] = bool(dry_run)
    context.setdefault("run_id", state.run_id)
    context.setdefault("log_dir", state.run_dir)
    context.setdefault("working_dir", "./.djx")
    context.setdefault("artifacts_dir", "./.djx")

    stage_args = dict(context.get("stage_args") or {})
    for stage_kind in (
        "build_noobscenes_inputs",
        "manual_box_annotation",
        "run_tracking",
    ):
        args = dict(stage_args.get(stage_kind) or {})
        args.setdefault("save_path_temp", save_path_temp)
        stage_args[stage_kind] = args

    projection_args = dict(stage_args.get("projection_and_trajectory") or {})
    projection_args.setdefault("save_path", save_path)
    projection_args.setdefault("save_path_temp", save_path_temp)
    stage_args["projection_and_trajectory"] = projection_args

    context["stage_args"] = stage_args
    return context


def _requested_agent_mode(params: Any) -> str:
    mode = str(
        _get_param(
            params,
            "agent_mode",
            None,
        )
        or _env_agent_mode()
        or AGENT_MODE_REACT
    ).strip()
    if mode not in {
        AGENT_MODE_REACT,
        AGENT_MODE_DETERMINISTIC,
        AGENT_MODE_REACT_WITH_FALLBACK,
    }:
        raise ValueError(f"unsupported VLA workflow agent_mode: {mode}")
    return mode


def _env_agent_mode() -> str:
    return os.environ.get("DJA_VLA_WORKFLOW_AGENT_MODE", "")


def _is_react_failure(exc: Exception) -> bool:
    from data_juicer_agents.capabilities.vla_workflow.react_agents import (
        VLAReActAgentUnavailable,
    )

    return isinstance(exc, VLAReActAgentUnavailable)


def _persist_execution_artifacts(state: VLAWorkflowState) -> None:
    if not state.run_dir:
        return
    run_dir = Path(state.run_dir).expanduser()
    if state.plan is not None:
        save_workflow_plan(run_dir, state.plan.model_dump())
    stage_results = [result.model_dump() for result in state.stage_results]
    (run_dir / STAGE_RESULTS_FILE).write_text(
        json.dumps(stage_results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _execute_confirmed_workflow(
    state: VLAWorkflowState,
    *,
    progress_callback: Callable[..., None] | None,
    tool_context: ToolContext | None = None,
    use_react: bool = False,
) -> VLAWorkflowState:
    updated = state.model_copy(deep=True)
    updated.runtime_context = _execution_context(updated, dry_run=False)

    while updated.status == "running":
        updated = select_next_stage(updated)
        if updated.route == "final_summary":
            updated = final_summary(updated)
            _persist_execution_artifacts(updated)
            return updated

        stage = _current_stage_payload(updated)
        _emit(
            progress_callback,
            "vla_stage_started",
            **stage,
            run_id=updated.run_id,
            run_dir=updated.run_dir,
            status=updated.status,
            summary=f"Executor-Agent: {stage.get('stage_id') or 'stage'} 开始",
        )

        updated = executor_agent_execute_stage(
            updated,
            tool_context=tool_context,
            use_react=use_react,
            progress_callback=progress_callback,
        )
        latest = updated.stage_results[-1] if updated.stage_results else None
        updated = update_state(updated)
        updated = route_after_stage(updated)
        _persist_execution_artifacts(updated)

        if latest is not None:
            event_type = (
                "vla_stage_paused"
                if latest.next_action == "pause"
                else "vla_stage_completed"
            )
            _emit(
                progress_callback,
                event_type,
                run_id=updated.run_id,
                run_dir=updated.run_dir,
                stage_id=latest.stage_id,
                tool=latest.tool,
                variant=latest.variant,
                status=latest.status,
                next_action=latest.next_action,
                summary=_stage_summary(latest, paused=latest.next_action == "pause"),
            )

        if updated.route == "final_summary":
            updated = final_summary(updated)
            _persist_execution_artifacts(updated)
            return updated
        if updated.route in {"paused", "failed", "plan_agent_read_docs"}:
            return updated

    _persist_execution_artifacts(updated)
    return updated


def execute_vla_workflow(
    params: Any,
    *,
    tool_context: ToolContext | None = None,
    progress_callback: Callable[..., None] | None = None,
) -> VLAWorkflowRunResult:
    try:
        requested_agent_mode = _requested_agent_mode(params)
    except ValueError as exc:
        return VLAWorkflowRunResult(
            exit_code=2,
            payload={
                "ok": False,
                "action": "vla_workflow_run",
                "agent_mode": AGENT_MODE_REACT,
                "requested_agent_mode": None,
                "fallback_used": False,
                "error_type": "invalid_agent_mode",
                "message": str(exc),
            },
        )
    active_agent_mode = (
        AGENT_MODE_DETERMINISTIC
        if requested_agent_mode == AGENT_MODE_DETERMINISTIC
        else AGENT_MODE_REACT
    )
    fallback_used = False
    fallback_reason = ""
    try:
        state = _planning_state(
            params,
            tool_context=tool_context,
            progress_callback=progress_callback,
            agent_mode=requested_agent_mode,
        )
    except Exception as exc:
        if requested_agent_mode == AGENT_MODE_REACT_WITH_FALLBACK and _is_react_failure(exc):
            fallback_used = True
            fallback_reason = str(exc)
            active_agent_mode = AGENT_MODE_DETERMINISTIC
            state = _planning_state(
                params,
                tool_context=tool_context,
                progress_callback=progress_callback,
                agent_mode=AGENT_MODE_DETERMINISTIC,
            )
            state.runtime_context["requested_agent_mode"] = requested_agent_mode
            state.runtime_context["agent_mode"] = AGENT_MODE_DETERMINISTIC
            state.runtime_context["fallback_used"] = True
            state.runtime_context["fallback_reason"] = fallback_reason
            state.messages.append(
                {
                    "type": "react_agent_fallback",
                    "reason": fallback_reason,
                    "agent_mode": AGENT_MODE_DETERMINISTIC,
                    "requested_agent_mode": requested_agent_mode,
                }
            )
        elif _is_react_failure(exc):
            return VLAWorkflowRunResult(
                exit_code=2,
                payload={
                    "ok": False,
                    "action": "vla_workflow_run",
                    "agent_mode": AGENT_MODE_REACT,
                    "requested_agent_mode": requested_agent_mode,
                    "fallback_used": False,
                    "error_type": "react_agent_unavailable",
                    "message": (
                        f"{exc}; deterministic fallback is disabled. "
                        "Set agent_mode='react-with-deterministic-fallback' or "
                        "agent_mode='deterministic' to use the deterministic workflow."
                    ),
                },
            )
        else:
            return VLAWorkflowRunResult(
                exit_code=2,
                payload={
                    "ok": False,
                    "action": "vla_workflow_run",
                    "agent_mode": active_agent_mode,
                    "requested_agent_mode": requested_agent_mode,
                    "fallback_used": fallback_used,
                    "error_type": "workflow_failed",
                    "message": str(exc),
                },
            )

    dry_run = bool(_get_param(params, "dry_run", False))
    if dry_run:
        exit_code = 0 if state.status != "failed" else 2
    elif state.status == "awaiting_confirmation" and not _get_param(params, "approve", False):
        exit_code = 3
    else:
        if _get_param(params, "approve", False) and state.status == "running":
            use_react_execution = state.runtime_context.get("agent_mode") == AGENT_MODE_REACT
            try:
                state = _execute_confirmed_workflow(
                    state,
                    progress_callback=progress_callback,
                    tool_context=tool_context,
                    use_react=use_react_execution,
                )
            except Exception as exc:
                if (
                    requested_agent_mode == AGENT_MODE_REACT_WITH_FALLBACK
                    and use_react_execution
                    and _is_react_failure(exc)
                ):
                    fallback_used = True
                    fallback_reason = str(exc)
                    state.runtime_context["agent_mode"] = AGENT_MODE_DETERMINISTIC
                    state.runtime_context["fallback_used"] = True
                    state.runtime_context["fallback_reason"] = fallback_reason
                    state.messages.append(
                        {
                            "type": "react_agent_fallback",
                            "reason": fallback_reason,
                            "agent_mode": AGENT_MODE_DETERMINISTIC,
                            "requested_agent_mode": requested_agent_mode,
                        }
                    )
                    state = _execute_confirmed_workflow(
                        state,
                        progress_callback=progress_callback,
                        tool_context=tool_context,
                        use_react=False,
                    )
                elif use_react_execution and _is_react_failure(exc):
                    state.status = "failed"
                    state.messages.append(
                        {
                            "type": "react_agent_unavailable",
                            "reason": str(exc),
                        }
                    )
                else:
                    raise
        exit_code = 0 if state.status != "failed" else 2

    payload = _payload(state, dry_run=dry_run, exit_code=exit_code)
    payload["agent_mode"] = state.runtime_context.get("agent_mode", active_agent_mode)
    payload["requested_agent_mode"] = state.runtime_context.get(
        "requested_agent_mode",
        requested_agent_mode,
    )
    payload["fallback_used"] = bool(state.runtime_context.get("fallback_used", fallback_used))
    if state.runtime_context.get("fallback_reason") or fallback_reason:
        payload["fallback_reason"] = str(
            state.runtime_context.get("fallback_reason") or fallback_reason
        )
    if exit_code == 3:
        payload["error_type"] = "approval_required"
        payload["message"] = "workflow plan requires approve before execution"
    elif state.status == "failed":
        payload["error_type"] = "workflow_failed"
        payload["message"] = "workflow failed"

    _emit_final_event(progress_callback, state, exit_code=exit_code)
    return VLAWorkflowRunResult(exit_code=exit_code, payload=payload)


def _current_stage_payload(state: VLAWorkflowState) -> dict[str, Any]:
    if state.plan is None or not state.current_stage_id:
        return {"stage_id": state.current_stage_id}
    for stage in state.plan.active_stages:
        if stage.id == state.current_stage_id:
            return {
                "stage_id": stage.id,
                "tool": stage.tool,
                "variant": stage.variant,
            }
    return {"stage_id": state.current_stage_id}


def _emit_final_event(
    progress_callback: Callable[..., None] | None,
    state: VLAWorkflowState,
    *,
    exit_code: int,
) -> None:
    if state.status == "failed" or exit_code == 2:
        event_type = "vla_workflow_failed"
    else:
        event_type = "vla_workflow_completed"
    _emit(
        progress_callback,
        event_type,
        run_id=state.run_id,
        run_dir=state.run_dir,
        status=state.status,
        stage_id=state.current_stage_id,
        summary=_user_message(state),
    )


def _plan_completed_summary(state: VLAWorkflowState) -> str:
    if state.plan is None:
        return "Plan-Agent: 处理计划生成失败"
    variants = []
    for stage in state.plan.active_stages:
        if stage.variant:
            variants.append(stage.variant)
    selected = " / ".join(dict.fromkeys(variants[:4]))
    if selected:
        return f"Plan-Agent: 已选择 {selected}"
    return "Plan-Agent: 已生成导航 VLA 处理计划"


def _stage_summary(stage_result: Any, *, paused: bool) -> str:
    if paused:
        return f"Executor-Agent: 等待人工标注 ({stage_result.stage_id})"
    if stage_result.status == "success":
        return f"Executor-Agent: {stage_result.stage_id} 完成"
    return f"Executor-Agent: {stage_result.stage_id} {stage_result.status}"


def _progress_summary(state: VLAWorkflowState) -> str:
    if not state.stage_results:
        return _plan_completed_summary(state)
    latest = state.stage_results[-1]
    return _stage_summary(latest, paused=latest.next_action == "pause")


def _user_message(state: VLAWorkflowState) -> str:
    prefix = ""
    if state.runtime_context.get("fallback_used"):
        prefix = (
            "Warning: real VLA ReAct agent was unavailable; deterministic fallback "
            f"was used. reason={state.runtime_context.get('fallback_reason')}. "
        )
    if state.status == "completed":
        return prefix + (
            f"VLA workflow completed: run_id={state.run_id}, "
            f"stages={len(state.stage_results)}, run_dir={state.run_dir}"
        )
    if state.status == "paused":
        return prefix + (
            f"VLA workflow paused at {state.current_stage_id}; "
            f"run_id={state.run_id}, run_dir={state.run_dir}"
        )
    if state.status == "awaiting_confirmation":
        return prefix + (
            f"VLA workflow plan is awaiting confirmation: run_id={state.run_id}, "
            f"run_dir={state.run_dir}"
        )
    if state.status == "failed":
        return prefix + f"VLA workflow failed: run_id={state.run_id}, run_dir={state.run_dir}"
    return prefix + f"VLA workflow status={state.status}: run_id={state.run_id}, run_dir={state.run_dir}"


__all__ = [
    "STAGE_RESULTS_FILE",
    "VLAWorkflowRunResult",
    "execute_vla_workflow",
]

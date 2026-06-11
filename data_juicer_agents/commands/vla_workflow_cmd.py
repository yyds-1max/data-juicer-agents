# -*- coding: utf-8 -*-
"""`djx vla-workflow` command handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_juicer_agents.capabilities.vla_workflow.graph import (
    VLAWorkflowState,
    ask_confirmation,
    generate_workflow_plan,
    initialize_state,
    plan_agent_fill_data_profile,
    plan_agent_inspect_loop,
    plan_agent_read_docs,
    save_observations,
    save_planning_notes,
    validate_data_profile,
    validate_plan_node,
)
from data_juicer_agents.capabilities.vla_workflow.persistence import (
    DATA_PROFILE_FILE,
    OBSERVATIONS_FILE,
    PLAN_FILE,
    PLANNING_NOTES_FILE,
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


def _emit_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _segments_arg(value: str | None) -> str | list[str]:
    raw = str(value or "all").strip()
    if not raw or raw.lower() == "all":
        return "all"
    return [item.strip() for item in raw.split(",") if item.strip()]


def _segments_for_tools(value: str | list[str]) -> list[str]:
    if value == "all":
        return []
    return list(value)


def _build_tool_context() -> ToolContext:
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


def _planning_state(args: Any) -> VLAWorkflowState:
    scenario = str(getattr(args, "scenario", "") or "navigation_vla").strip()
    selected_segments = _segments_arg(getattr(args, "segments", None))
    user_inputs: dict[str, Any] = {
        "scenario": scenario,
        "date": str(getattr(args, "date", "") or "").strip(),
        "selected_segments": selected_segments,
        "scene_mode": str(getattr(args, "scene_mode", "") or "out").strip(),
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
            f"segments {getattr(args, 'segments', 'all')}."
        ),
        scenario=scenario,
        user_inputs=user_inputs,
        run_id=str(getattr(args, "run_id", "") or "").strip(),
        approval_status="approved" if getattr(args, "approve", False) else "not_required",
    )
    state = initialize_state(state, tool_context=_build_tool_context())

    if scenario == "navigation_vla":
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
    return ask_confirmation(state)


def _artifact_paths(state: VLAWorkflowState) -> dict[str, str]:
    run_dir = Path(state.run_dir).expanduser()
    return {
        "planning_notes": str(run_dir / PLANNING_NOTES_FILE),
        "observations": str(run_dir / OBSERVATIONS_FILE),
        "data_profile": str(run_dir / DATA_PROFILE_FILE),
        "plan": str(run_dir / PLAN_FILE),
    }


def _payload(state: VLAWorkflowState, *, dry_run: bool, exit_code: int) -> dict[str, Any]:
    plan = state.plan
    return {
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
        "artifacts": _artifact_paths(state),
        "messages": state.messages,
    }


def run_vla_workflow(args: Any) -> int:
    action = str(getattr(args, "vla_workflow_action", "") or "").strip()
    if action != "run":
        _emit_json(
            {
                "ok": False,
                "action": "vla_workflow",
                "error_type": "unknown_action",
                "message": f"unknown vla-workflow action: {action}",
            }
        )
        return 2

    try:
        state = _planning_state(args)
    except Exception as exc:
        _emit_json(
            {
                "ok": False,
                "action": "vla_workflow_run",
                "error_type": "workflow_failed",
                "message": str(exc),
            }
        )
        return 2

    dry_run = bool(getattr(args, "dry_run", False))
    if dry_run:
        exit_code = 0 if state.status != "failed" else 2
    elif state.status == "awaiting_confirmation" and not getattr(args, "approve", False):
        exit_code = 3
    else:
        exit_code = 0 if state.status != "failed" else 2

    payload = _payload(state, dry_run=dry_run, exit_code=exit_code)
    if exit_code == 3:
        payload["error_type"] = "approval_required"
        payload["message"] = "workflow plan requires --approve before execution"
    elif state.status == "failed":
        payload["error_type"] = "workflow_failed"
        payload["message"] = "workflow planning failed"
    _emit_json(payload)
    return exit_code

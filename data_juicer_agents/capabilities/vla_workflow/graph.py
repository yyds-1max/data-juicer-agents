from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from data_juicer_agents.capabilities.vla_workflow.catalog.model import ToolCapability
from data_juicer_agents.capabilities.vla_workflow.executor_agent import (
    VLAStageResult,
    execute_stage,
)
from data_juicer_agents.capabilities.vla_workflow.persistence import (
    OBSERVATIONS_FILE,
    PLAN_FILE,
    build_workflow_run_dir,
    make_workflow_run_id,
    save_data_profile as persist_data_profile,
    save_planning_notes as persist_planning_notes,
    save_workflow_plan as persist_workflow_plan,
)
from data_juicer_agents.capabilities.vla_workflow.plan import validate_plan
from data_juicer_agents.capabilities.vla_workflow.plan.model import (
    VLAWorkflowPlan,
    VLAWorkflowStage,
)
from data_juicer_agents.capabilities.vla_workflow.plan_agent import (
    NAVIGATION_RULE_DOC,
    build_planning_notes,
    deterministic_plan_vla_workflow,
)
from data_juicer_agents.capabilities.vla_workflow.profile.validate_navigation import (
    validate_navigation_data_profile_model,
)
from data_juicer_agents.capabilities.vla_workflow.state import PlanAgentMemory
from data_juicer_agents.core.tool import ToolContext, get_tool_spec

ApprovalStatus = Literal["not_required", "pending", "approved", "rejected"]
WorkflowStatus = Literal[
    "planning",
    "awaiting_confirmation",
    "running",
    "paused",
    "completed",
    "failed",
]


class VLAWorkflowState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    user_request: str = ""
    scenario: str | None = None
    user_inputs: dict[str, Any] = Field(default_factory=dict)
    run_id: str = ""
    run_dir: str = ""
    plan_agent_memory: PlanAgentMemory = Field(default_factory=PlanAgentMemory)
    planning_notes_ref: str | None = None
    observations_ref: str | None = None
    data_profile_ref: str | None = None
    plan_ref: str | None = None
    plan: VLAWorkflowPlan | None = None
    current_stage_id: str | None = None
    stage_results: list[VLAStageResult] = Field(default_factory=list)
    approval_status: ApprovalStatus = "not_required"
    status: WorkflowStatus = "planning"
    messages: list[dict[str, Any]] = Field(default_factory=list)

    observations: list[dict[str, Any]] = Field(default_factory=list)
    data_profile: Any | None = None
    runtime_context: dict[str, Any] = Field(default_factory=dict)
    retry_counts: dict[str, int] = Field(default_factory=dict)
    route: str | None = None
    routed_stage_result_count: int = 0


def initialize_state(
    state: VLAWorkflowState | Mapping[str, Any],
    *,
    tool_context: ToolContext | None = None,
    created_at: datetime | None = None,
) -> VLAWorkflowState:
    updated = _as_state(state)
    scenario = str(
        updated.scenario or updated.user_inputs.get("scenario") or "navigation_vla"
    )
    date = str(updated.user_inputs.get("date") or "unknown")
    updated.scenario = scenario
    updated.plan_agent_memory.scenario = scenario
    updated.plan_agent_memory.user_inputs = dict(updated.user_inputs)

    if not updated.run_id:
        updated.run_id = make_workflow_run_id(
            scenario=scenario,
            date=date,
            created_at=created_at,
        )
    if not updated.run_dir:
        updated.run_dir = str(
            build_workflow_run_dir(
                tool_context,
                scenario=scenario,
                date=date,
                run_id=updated.run_id,
                created_at=created_at,
            )
        )
    updated.runtime_context.setdefault("run_id", updated.run_id)
    updated.runtime_context.setdefault("log_dir", updated.run_dir)
    updated.status = "planning"
    _add_message(updated, "workflow_initialized", run_id=updated.run_id)
    return updated


def plan_agent_read_docs(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    docs = [NAVIGATION_RULE_DOC] if updated.scenario == "navigation_vla" else []
    updated.plan_agent_memory.source_docs = docs
    updated.plan_agent_memory.planning_notes = build_planning_notes(
        user_inputs=updated.user_inputs,
        scenario=updated.scenario or "navigation_vla",
        source_docs=docs,
    )
    updated.status = "planning"
    _add_message(updated, "plan_agent_read_docs", source_docs=docs)
    return updated


def save_planning_notes(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    notes = updated.plan_agent_memory.planning_notes or build_planning_notes(
        user_inputs=updated.user_inputs,
        scenario=updated.scenario or "navigation_vla",
        source_docs=updated.plan_agent_memory.source_docs,
    )
    updated.plan_agent_memory.planning_notes = notes
    if updated.run_dir:
        updated.planning_notes_ref = str(
            persist_planning_notes(Path(updated.run_dir), notes).name
        )
    else:
        updated.planning_notes_ref = "planning_notes.json"
    _add_message(updated, "planning_notes_saved", ref=updated.planning_notes_ref)
    return updated


def plan_agent_inspect_loop(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    supplied = updated.user_inputs.get("observations")
    if isinstance(supplied, list) and not updated.observations:
        updated.observations = [
            dict(item) for item in supplied if isinstance(item, Mapping)
        ]
    updated.plan_agent_memory.observations = list(updated.observations)
    _add_message(updated, "plan_agent_inspect_loop", count=len(updated.observations))
    return updated


def save_observations(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    updated.observations_ref = OBSERVATIONS_FILE
    if updated.run_dir:
        path = Path(updated.run_dir).expanduser() / OBSERVATIONS_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(updated.observations, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    _add_message(updated, "observations_saved", ref=updated.observations_ref)
    return updated


def plan_agent_fill_data_profile(
    state: VLAWorkflowState | Mapping[str, Any],
    *,
    catalog: Iterable[ToolCapability] | None = None,
) -> VLAWorkflowState:
    updated = _as_state(state)
    result = deterministic_plan_vla_workflow(
        user_inputs={
            **updated.user_inputs,
            "scenario": updated.scenario or updated.user_inputs.get("scenario"),
        },
        observations=updated.observations,
        catalog=catalog,
    )
    updated.plan_agent_memory = result["memory"]
    updated.data_profile = result["data_profile"]
    updated.plan = result["plan"]
    _add_message(
        updated,
        "data_profile_filled",
        has_profile=updated.data_profile is not None,
    )
    return updated


def validate_data_profile(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    if updated.data_profile is None:
        updated.status = "failed"
        _add_message(updated, "data_profile_invalid", errors=["missing_data_profile"])
        return updated
    if updated.scenario != "navigation_vla":
        _add_message(
            updated, "data_profile_validation_skipped", scenario=updated.scenario
        )
        return updated

    validation = validate_navigation_data_profile_model(updated.data_profile)
    if not validation["ok"]:
        updated.status = "failed"
        _add_message(
            updated,
            "data_profile_invalid",
            errors=validation["errors"],
            warnings=validation["warnings"],
        )
        return updated
    if updated.run_dir:
        payload = _plain_data(updated.data_profile)
        updated.data_profile_ref = str(
            persist_data_profile(Path(updated.run_dir), payload).name
        )
    else:
        updated.data_profile_ref = "data_profile.json"
    _add_message(updated, "data_profile_valid", ref=updated.data_profile_ref)
    return updated


def generate_workflow_plan(
    state: VLAWorkflowState | Mapping[str, Any],
    *,
    catalog: Iterable[ToolCapability] | None = None,
) -> VLAWorkflowState:
    updated = _as_state(state)
    if updated.plan is None:
        result = deterministic_plan_vla_workflow(
            user_inputs={
                **updated.user_inputs,
                "scenario": updated.scenario or updated.user_inputs.get("scenario"),
            },
            observations=updated.observations,
            catalog=catalog,
        )
        updated.plan_agent_memory = result["memory"]
        updated.data_profile = result["data_profile"]
        updated.plan = result["plan"]
    if updated.run_dir and updated.plan is not None:
        updated.plan_ref = str(
            persist_workflow_plan(
                Path(updated.run_dir),
                updated.plan.model_dump(),
            ).name
        )
    else:
        updated.plan_ref = PLAN_FILE
    _add_message(
        updated,
        "workflow_plan_generated",
        plan_id=updated.plan.plan_id if updated.plan else None,
    )
    return updated


def validate_plan_node(
    state: VLAWorkflowState | Mapping[str, Any],
    *,
    catalog: Iterable[ToolCapability] | None = None,
) -> VLAWorkflowState:
    updated = _as_state(state)
    if updated.plan is None:
        updated.status = "failed"
        _add_message(updated, "plan_invalid", errors=["missing_plan"])
        return updated
    validation = validate_plan(updated.plan, catalog=catalog)
    if not validation["ok"]:
        updated.status = "failed"
        _add_message(
            updated,
            "plan_invalid",
            errors=validation["errors"],
            warnings=validation["warnings"],
        )
        return updated
    _add_message(updated, "plan_valid", warnings=validation["warnings"])
    return updated


def ask_confirmation(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    if updated.plan is None:
        updated.status = "failed"
        _add_message(updated, "approval_failed", reason="missing_plan")
        return updated
    if updated.plan.status == "failed":
        updated.status = "failed"
        updated.approval_status = "not_required"
        updated.route = "failed"
        _add_message(updated, "approval_skipped", reason="plan_failed")
        return updated

    stage_ids = _approval_stage_ids(updated.plan)
    if not stage_ids:
        updated.approval_status = "not_required"
        updated.status = "running"
        updated.route = "select_next_stage"
        _add_message(updated, "approval_not_required")
        return updated

    if updated.approval_status == "approved":
        updated.status = "running"
        updated.plan.status = "confirmed"
        updated.route = "select_next_stage"
        _add_message(updated, "approval_accepted", stage_ids=stage_ids)
        return updated
    if updated.approval_status == "rejected":
        updated.status = "failed"
        updated.plan.status = "failed"
        updated.route = "failed"
        _add_message(updated, "approval_rejected", stage_ids=stage_ids)
        return updated

    updated.approval_status = "pending"
    updated.status = "awaiting_confirmation"
    updated.route = "awaiting_confirmation"
    _add_message(
        updated,
        "approval_required",
        stage_ids=stage_ids,
        summary=_plan_summary(updated.plan),
    )
    return updated


def select_next_stage(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    if updated.status in {"awaiting_confirmation", "paused", "completed", "failed"}:
        return updated
    if updated.plan is None:
        updated.status = "failed"
        updated.route = "failed"
        _add_message(updated, "stage_selection_failed", reason="missing_plan")
        return updated
    if _confirmation_blocks_execution(updated):
        updated.status = "awaiting_confirmation"
        updated.route = "awaiting_confirmation"
        return updated

    for stage in updated.plan.active_stages:
        if stage.status in {"pending", "failed"}:
            stage.status = "running"
            updated.current_stage_id = stage.id
            updated.status = "running"
            updated.route = "executor_agent_execute_stage"
            _add_message(updated, "stage_selected", stage_id=stage.id)
            return updated

    updated.current_stage_id = None
    updated.route = "final_summary"
    return updated


def executor_agent_execute_stage(
    state: VLAWorkflowState | Mapping[str, Any],
    *,
    registry: Any | None = None,
    catalog: Iterable[ToolCapability] | None = None,
    tool_context: ToolContext | None = None,
    use_react: bool = False,
    progress_callback: Any | None = None,
) -> VLAWorkflowState:
    updated = _as_state(state)
    if _confirmation_blocks_execution(updated):
        updated.status = "awaiting_confirmation"
        updated.route = "awaiting_confirmation"
        _add_message(updated, "executor_blocked", reason="approval_pending")
        return updated
    if updated.plan is None:
        updated.status = "failed"
        updated.route = "failed"
        _add_message(updated, "executor_failed", reason="missing_plan")
        return updated
    stage = _current_stage(updated)
    if stage is None:
        updated = select_next_stage(updated)
        stage = _current_stage(updated)
    if stage is None:
        updated.route = "final_summary"
        return updated
    if updated.data_profile is None:
        updated.status = "failed"
        updated.route = "failed"
        _add_message(updated, "executor_failed", reason="missing_data_profile")
        return updated

    if use_react:
        from data_juicer_agents.capabilities.vla_workflow.react_agents import (
            run_executor_agent_react,
        )

        result = run_executor_agent_react(
            current_stage=stage,
            data_profile=updated.data_profile,
            observations=updated.observations,
            previous_stage_outputs=_previous_stage_outputs(updated),
            runtime_context=_runtime_context(updated),
            tool_capability=_current_stage_capability(stage, catalog),
            tool_spec=_get_tool_spec_for_stage(stage.tool, registry),
            tool_context=tool_context or _tool_context_from_state(updated),
            progress_callback=progress_callback,
        )
    else:
        result = execute_stage(
            plan=updated.plan,
            current_stage=stage,
            data_profile=updated.data_profile,
            observations=updated.observations,
            previous_stage_outputs=_previous_stage_outputs(updated),
            runtime_context=_runtime_context(updated),
            registry=registry,
            catalog=catalog,
            tool_context=tool_context,
        )
    updated.stage_results.append(result)
    updated.route = "update_state"
    _add_message(
        updated,
        "stage_executed",
        stage_id=result.stage_id,
        status=result.status,
        next_action=result.next_action,
    )
    return updated


def update_state(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    result = _latest_result(updated)
    if result is None:
        return updated
    stage = _stage_by_id(updated.plan, result.stage_id)
    if stage is not None:
        if result.status == "success":
            stage.status = "success"
        elif result.next_action == "stop":
            stage.status = "failed"
        elif result.next_action == "retry":
            stage.status = "pending"
        elif result.next_action == "pause":
            stage.status = "running"
        elif result.next_action == "replan":
            stage.status = "failed"
    updated.current_stage_id = result.stage_id
    _add_message(
        updated,
        "stage_state_updated",
        stage_id=result.stage_id,
        status=result.status,
        next_action=result.next_action,
    )
    return updated


def route_after_stage(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    result = _latest_result(updated)
    if result is None:
        updated.route = "select_next_stage"
        return updated

    action = result.next_action
    if action == "continue":
        if _all_stages_finished(updated):
            updated.route = "final_summary"
        else:
            updated.route = "select_next_stage"
        updated.status = "running"
        return updated

    if action == "retry":
        retry_count = updated.retry_counts.get(result.stage_id, 0)
        if len(updated.stage_results) > updated.routed_stage_result_count:
            retry_count += 1
            updated.retry_counts[result.stage_id] = retry_count
            updated.routed_stage_result_count = len(updated.stage_results)
        max_retries = _max_stage_retries(updated)
        if retry_count <= max_retries:
            updated.status = "running"
            updated.current_stage_id = result.stage_id
            updated.route = "executor_agent_execute_stage"
            _add_message(
                updated,
                "stage_retry_scheduled",
                stage_id=result.stage_id,
                retry_count=retry_count,
                max_retries=max_retries,
            )
            return updated

        updated.status = "failed"
        updated.route = "failed"
        _mark_stage_failed(updated, result.stage_id)
        if updated.plan is not None:
            updated.plan.status = "failed"
        _add_message(
            updated,
            "retry_limit_exceeded",
            stage_id=result.stage_id,
            retry_count=retry_count,
            max_retries=max_retries,
        )
        return updated

    if action == "pause":
        updated.status = "paused"
        updated.route = "paused"
        updated.current_stage_id = result.stage_id
        _add_message(updated, "workflow_paused", stage_id=result.stage_id)
        return updated

    if action == "replan":
        updated.status = "planning"
        updated.route = "plan_agent_read_docs"
        _mark_stage_failed(updated, result.stage_id)
        _add_message(updated, "replan_requested", stage_id=result.stage_id)
        return updated

    updated.status = "failed"
    updated.route = "failed"
    _mark_stage_failed(updated, result.stage_id)
    if updated.plan is not None:
        updated.plan.status = "failed"
    _add_message(updated, "workflow_failed", stage_id=result.stage_id)
    return updated


def final_summary(
    state: VLAWorkflowState | Mapping[str, Any],
) -> VLAWorkflowState:
    updated = _as_state(state)
    if updated.status != "failed":
        updated.status = "completed"
        if updated.plan is not None:
            updated.plan.status = "completed"
        _add_message(
            updated,
            "workflow_completed",
            stage_count=len(updated.stage_results),
            artifact_count=sum(
                len(result.artifacts) for result in updated.stage_results
            ),
        )
        updated.route = "end"
        return updated

    _add_message(
        updated, "workflow_failed_summary", stage_count=len(updated.stage_results)
    )
    updated.route = "end"
    return updated


class DeterministicVLAWorkflowGraph:
    def invoke(
        self,
        state: VLAWorkflowState | Mapping[str, Any],
        config: Mapping[str, Any] | None = None,
    ) -> VLAWorkflowState:
        options = dict((config or {}).get("configurable", {}) or {})
        updated = initialize_state(
            state,
            tool_context=options.get("tool_context"),
            created_at=options.get("created_at"),
        )
        updated = plan_agent_read_docs(updated)
        updated = save_planning_notes(updated)
        updated = plan_agent_inspect_loop(updated)
        updated = save_observations(updated)
        updated = plan_agent_fill_data_profile(updated, catalog=options.get("catalog"))
        updated = validate_data_profile(updated)
        if updated.status == "failed":
            return updated
        updated = generate_workflow_plan(updated, catalog=options.get("catalog"))
        updated = validate_plan_node(updated, catalog=options.get("catalog"))
        if updated.status == "failed":
            return updated
        updated = ask_confirmation(updated)
        if updated.status == "awaiting_confirmation":
            return updated

        while updated.status == "running":
            updated = select_next_stage(updated)
            if updated.route == "final_summary":
                return final_summary(updated)
            updated = executor_agent_execute_stage(
                updated,
                registry=options.get("registry"),
                catalog=options.get("catalog"),
                tool_context=options.get("tool_context"),
            )
            updated = update_state(updated)
            updated = route_after_stage(updated)
            if updated.route == "final_summary":
                return final_summary(updated)
            if updated.route in {"paused", "failed", "plan_agent_read_docs"}:
                return updated
        return updated


def build_vla_workflow_graph() -> Any:
    try:
        from langgraph.graph import END, StateGraph
    except ModuleNotFoundError:
        return DeterministicVLAWorkflowGraph()

    graph = StateGraph(VLAWorkflowState)
    graph.add_node("initialize_state", initialize_state)
    graph.add_node("plan_agent_read_docs", plan_agent_read_docs)
    graph.add_node("save_planning_notes", save_planning_notes)
    graph.add_node("plan_agent_inspect_loop", plan_agent_inspect_loop)
    graph.add_node("save_observations", save_observations)
    graph.add_node("plan_agent_fill_data_profile", plan_agent_fill_data_profile)
    graph.add_node("validate_data_profile", validate_data_profile)
    graph.add_node("generate_workflow_plan", generate_workflow_plan)
    graph.add_node("validate_plan_node", validate_plan_node)
    graph.add_node("ask_confirmation", ask_confirmation)
    graph.add_node("select_next_stage", select_next_stage)
    graph.add_node("executor_agent_execute_stage", executor_agent_execute_stage)
    graph.add_node("update_state", update_state)
    graph.add_node("route_after_stage", route_after_stage)
    graph.add_node("final_summary", final_summary)

    graph.set_entry_point("initialize_state")
    graph.add_edge("initialize_state", "plan_agent_read_docs")
    graph.add_edge("plan_agent_read_docs", "save_planning_notes")
    graph.add_edge("save_planning_notes", "plan_agent_inspect_loop")
    graph.add_edge("plan_agent_inspect_loop", "save_observations")
    graph.add_edge("save_observations", "plan_agent_fill_data_profile")
    graph.add_edge("plan_agent_fill_data_profile", "validate_data_profile")
    graph.add_conditional_edges(
        "validate_data_profile",
        _route_after_validation,
        {"failed": END, "generate_workflow_plan": "generate_workflow_plan"},
    )
    graph.add_edge("generate_workflow_plan", "validate_plan_node")
    graph.add_conditional_edges(
        "validate_plan_node",
        _route_after_validation,
        {"failed": END, "generate_workflow_plan": "ask_confirmation"},
    )
    graph.add_conditional_edges(
        "ask_confirmation",
        _route_after_confirmation,
        {
            "awaiting_confirmation": END,
            "failed": END,
            "select_next_stage": "select_next_stage",
        },
    )
    graph.add_conditional_edges(
        "select_next_stage",
        _route_after_selection,
        {
            "executor_agent_execute_stage": "executor_agent_execute_stage",
            "final_summary": "final_summary",
            "awaiting_confirmation": END,
            "failed": END,
        },
    )
    graph.add_edge("executor_agent_execute_stage", "update_state")
    graph.add_edge("update_state", "route_after_stage")
    graph.add_conditional_edges(
        "route_after_stage",
        _route_after_stage_node,
        {
            "select_next_stage": "select_next_stage",
            "executor_agent_execute_stage": "executor_agent_execute_stage",
            "plan_agent_read_docs": "plan_agent_read_docs",
            "final_summary": "final_summary",
            "paused": END,
            "failed": END,
        },
    )
    graph.add_edge("final_summary", END)
    return graph.compile()


def _as_state(state: VLAWorkflowState | Mapping[str, Any]) -> VLAWorkflowState:
    if isinstance(state, VLAWorkflowState):
        return state.model_copy(deep=True)
    return VLAWorkflowState.model_validate(dict(state))


def _plain_data(value: Any) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _add_message(state: VLAWorkflowState, message_type: str, **payload: Any) -> None:
    message = {"type": message_type}
    message.update(payload)
    state.messages.append(message)


def _approval_stage_ids(plan: VLAWorkflowPlan) -> list[str]:
    return [
        stage.id
        for stage in plan.active_stages
        if stage.effects in {"write", "execute", "external"}
    ]


def _plan_summary(plan: VLAWorkflowPlan) -> dict[str, Any]:
    return {
        "plan_id": plan.plan_id,
        "scenario": plan.scenario,
        "active_stage_count": len(plan.active_stages),
        "skipped_stage_count": len(plan.skipped_stages),
        "approval_required": plan.approval_required,
    }


def _confirmation_blocks_execution(state: VLAWorkflowState) -> bool:
    if state.plan is None:
        return False
    return bool(_approval_stage_ids(state.plan)) and state.approval_status != "approved"


def _current_stage(state: VLAWorkflowState) -> VLAWorkflowStage | None:
    return _stage_by_id(state.plan, state.current_stage_id)


def _stage_by_id(
    plan: VLAWorkflowPlan | None,
    stage_id: str | None,
) -> VLAWorkflowStage | None:
    if plan is None or not stage_id:
        return None
    for stage in plan.active_stages:
        if stage.id == stage_id:
            return stage
    return None


def _latest_result(state: VLAWorkflowState) -> VLAStageResult | None:
    if not state.stage_results:
        return None
    return state.stage_results[-1]


def _previous_stage_outputs(state: VLAWorkflowState) -> dict[str, Any]:
    return {
        result.stage_id: result.tool_result
        for result in state.stage_results
        if result.status == "success"
    }


def _runtime_context(state: VLAWorkflowState) -> dict[str, Any]:
    context = dict(state.runtime_context)
    context.setdefault("run_id", state.run_id)
    context.setdefault("log_dir", state.run_dir)
    return context


def _current_stage_capability(
    stage: VLAWorkflowStage,
    catalog: Iterable[ToolCapability] | None,
) -> ToolCapability | None:
    for capability in catalog or []:
        if capability.tool == stage.tool and capability.stage_kind == stage.stage_kind:
            return capability
    return None


def _get_tool_spec_for_stage(tool_name: str, registry: Any | None) -> Any:
    if registry is None:
        return get_tool_spec(tool_name)
    if hasattr(registry, "get"):
        return registry.get(tool_name)
    return registry[tool_name]


def _tool_context_from_state(state: VLAWorkflowState) -> ToolContext:
    context = _runtime_context(state)
    return ToolContext(
        working_dir=str(context.get("working_dir") or "./.djx"),
        artifacts_dir=str(context.get("artifacts_dir") or "./.djx"),
        env=dict(context.get("env") or {}),
        runtime_values=dict(context.get("runtime_values") or {}),
    )


def _max_stage_retries(state: VLAWorkflowState) -> int:
    raw = state.runtime_context.get("max_stage_retries", 1)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 1


def _all_stages_finished(state: VLAWorkflowState) -> bool:
    if state.plan is None:
        return False
    return all(
        stage.status in {"success", "skipped"} for stage in state.plan.active_stages
    )


def _mark_stage_failed(state: VLAWorkflowState, stage_id: str) -> None:
    stage = _stage_by_id(state.plan, stage_id)
    if stage is not None:
        stage.status = "failed"


def _route_after_validation(state: VLAWorkflowState) -> str:
    if state.status == "failed":
        return "failed"
    return "generate_workflow_plan"


def _route_after_confirmation(state: VLAWorkflowState) -> str:
    if state.status == "awaiting_confirmation":
        return "awaiting_confirmation"
    if state.status == "failed":
        return "failed"
    return "select_next_stage"


def _route_after_selection(state: VLAWorkflowState) -> str:
    if state.status == "awaiting_confirmation":
        return "awaiting_confirmation"
    if state.status == "failed":
        return "failed"
    if state.route == "final_summary":
        return "final_summary"
    return "executor_agent_execute_stage"


def _route_after_stage_node(state: VLAWorkflowState) -> str:
    return state.route or "failed"


__all__ = [
    "ApprovalStatus",
    "DeterministicVLAWorkflowGraph",
    "VLAWorkflowState",
    "WorkflowStatus",
    "ask_confirmation",
    "build_vla_workflow_graph",
    "executor_agent_execute_stage",
    "final_summary",
    "generate_workflow_plan",
    "initialize_state",
    "plan_agent_fill_data_profile",
    "plan_agent_inspect_loop",
    "plan_agent_read_docs",
    "route_after_stage",
    "save_observations",
    "save_planning_notes",
    "select_next_stage",
    "update_state",
    "validate_data_profile",
    "validate_plan_node",
]

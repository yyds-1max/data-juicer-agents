from __future__ import annotations

import json
import os
import re
import asyncio
import inspect
import threading
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import ValidationError

from data_juicer_agents.adapters.agentscope.tools import (
    build_agentscope_json_schema,
    build_agentscope_tool_function,
)
from data_juicer_agents.capabilities.vla_workflow.catalog.model import ToolCapability
from data_juicer_agents.capabilities.vla_workflow.catalog.service import (
    list_tool_capabilities,
)
from data_juicer_agents.capabilities.vla_workflow.executor_agent import VLAStageResult
from data_juicer_agents.capabilities.vla_workflow.plan.model import VLAWorkflowPlan
from data_juicer_agents.capabilities.vla_workflow.plan.validate import validate_plan
from data_juicer_agents.capabilities.vla_workflow.plan_agent import (
    build_observation,
)
from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationVLADataProfile,
)
from data_juicer_agents.capabilities.vla_workflow.profile.validate_navigation import (
    validate_navigation_data_profile_model,
)
from data_juicer_agents.capabilities.vla_workflow.state import PlanAgentMemory
from data_juicer_agents.core.tool import ToolContext, ToolSpec, get_tool_spec

_DEFAULT_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_MODEL = "qwen3-max-2026-01-23"
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_MAX_PLAN_REPAIR_ATTEMPTS = 3


class VLAReActAgentUnavailable(RuntimeError):
    """Raised when the real VLA ReAct agents cannot be initialized or called."""


class VLAReActPlanValidationError(VLAReActAgentUnavailable):
    """Raised when Plan-Agent drafts remain invalid after repair attempts."""

    def __init__(
        self,
        message: str,
        *,
        planning_notes: Mapping[str, Any],
        observations: list[dict[str, Any]],
        validation_feedback: Mapping[str, Any] | None,
    ) -> None:
        super().__init__(message)
        self.planning_notes = dict(planning_notes)
        self.observations = list(observations)
        self.validation_feedback = dict(validation_feedback or {})


@dataclass(frozen=True)
class VLAReActModelConfig:
    model_name: str
    api_key: str
    base_url: str
    thinking: bool


def ensure_react_agents_available() -> None:
    _model_config("plan")


def run_plan_agent_react(
    *,
    user_request: str,
    scenario: str,
    user_inputs: Mapping[str, Any],
    planning_notes: Mapping[str, Any],
    source_docs: list[str],
    tool_context: ToolContext,
    progress_callback: Callable[..., None] | None = None,
    catalog: Iterable[ToolCapability] | None = None,
) -> dict[str, Any]:
    collected_observations: list[dict[str, Any]] = []
    resolved_catalog = list(catalog) if catalog is not None else list_tool_capabilities(
        scenario=scenario
    )
    tool_specs = _plan_tool_specs(resolved_catalog)
    agent = _build_react_agent(
        name="VLAPlanReActAgent",
        sys_prompt=_plan_sys_prompt(),
        agent_kind="plan",
        tool_specs=tool_specs,
        tool_context=tool_context,
        progress_callback=progress_callback,
        observation_collector=collected_observations,
    )
    observations: list[dict[str, Any]] = []
    profile_draft: dict[str, Any] = {}
    plan_draft: dict[str, Any] = {}
    validation_feedback: dict[str, Any] | None = None
    memory = PlanAgentMemory(
        scenario=scenario,
        user_inputs=dict(user_inputs),
        source_docs=list(source_docs),
        planning_notes=dict(planning_notes),
    )

    for attempt in range(_MAX_PLAN_REPAIR_ATTEMPTS + 1):
        reply_text = _run_agent(
            agent,
            _plan_agent_input_payload(
                user_request=user_request,
                scenario=scenario,
                user_inputs=user_inputs,
                source_docs=source_docs,
                planning_notes=memory.planning_notes,
                catalog=resolved_catalog,
                observations=observations,
                profile_draft=profile_draft,
                plan_draft=plan_draft,
                validation_feedback=validation_feedback,
                repair_attempt=attempt,
            ),
        )
        payload = _parse_json_object(reply_text)
        observations = _observations_from_payload(payload, collected_observations)
        profile_draft = dict(payload.get("data_profile") or profile_draft)
        plan_draft = dict(payload.get("plan") or plan_draft)
        memory = PlanAgentMemory(
            scenario=scenario,
            user_inputs=dict(user_inputs),
            source_docs=list(source_docs),
            planning_notes=dict(payload.get("planning_notes") or memory.planning_notes),
            observations=observations,
            data_profile_draft=profile_draft,
            decisions=list(payload.get("decisions") or memory.decisions),
        )
        validation = _validate_plan_agent_drafts(
            data_profile_payload=profile_draft,
            plan_payload=plan_draft,
            catalog=resolved_catalog,
        )
        if validation["ok"]:
            memory.ready_to_plan = True
            return {
                "memory": memory,
                "planning_notes": memory.planning_notes,
                "observations": observations,
                "data_profile": validation["data_profile"],
                "plan": validation["plan"],
            }
        validation_feedback = validation

    raise VLAReActPlanValidationError(
        (
            "VLA Plan-Agent draft validation failed after "
            f"{_MAX_PLAN_REPAIR_ATTEMPTS} repair attempts: "
            f"{json.dumps(validation_feedback, ensure_ascii=False)}"
        ),
        planning_notes=memory.planning_notes,
        observations=observations,
        validation_feedback=validation_feedback,
    )


def run_executor_agent_react(
    *,
    current_stage: Any,
    data_profile: Any,
    observations: list[dict[str, Any]],
    previous_stage_outputs: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    tool_capability: ToolCapability | None,
    tool_spec: ToolSpec,
    tool_context: ToolContext,
    progress_callback: Callable[..., None] | None = None,
) -> VLAStageResult:
    captured: dict[str, Any] = {}
    agent = _build_react_agent(
        name="VLAExecutorReActAgent",
        sys_prompt=_executor_sys_prompt(),
        agent_kind="executor",
        tool_specs=[tool_spec],
        tool_context=tool_context,
        progress_callback=progress_callback,
        stage_tool_capture=captured,
    )
    reply_text = _run_agent(
        agent,
        {
            "current_stage": _plain(current_stage),
            "data_profile": _plain(data_profile),
            "observations": observations,
            "previous_stage_outputs": dict(previous_stage_outputs),
            "runtime_context": dict(runtime_context),
            "tool_capability": _plain(tool_capability) if tool_capability else None,
            "tool_input_schema": tool_spec.input_model.model_json_schema(),
            "required_output_schema": VLAStageResult.model_json_schema(),
        },
    )
    payload = _parse_json_object(reply_text)
    if "tool_result" not in payload and captured.get("tool_result") is not None:
        payload["tool_result"] = captured["tool_result"]
    if "tool_args_preview" not in payload and captured.get("tool_args_preview") is not None:
        payload["tool_args_preview"] = captured["tool_args_preview"]
    return VLAStageResult.model_validate(payload)


def _model_config(agent_kind: str) -> VLAReActModelConfig:
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MODELSCOPE_API_TOKEN")
    if not api_key:
        raise VLAReActAgentUnavailable(
            "Missing API key: set DASHSCOPE_API_KEY or MODELSCOPE_API_TOKEN"
        )
    model_env = (
        "DJA_VLA_PLAN_MODEL" if agent_kind == "plan" else "DJA_VLA_EXECUTOR_MODEL"
    )
    model_name = (
        os.environ.get(model_env)
        or os.environ.get("DJA_SESSION_MODEL")
        or os.environ.get("DJA_PLANNER_MODEL")
        or _DEFAULT_MODEL
    )
    thinking = os.environ.get("DJA_LLM_THINKING", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    return VLAReActModelConfig(
        model_name=str(model_name).strip() or _DEFAULT_MODEL,
        api_key=str(api_key).strip(),
        base_url=os.environ.get("DJA_OPENAI_BASE_URL", _DEFAULT_BASE_URL),
        thinking=thinking,
    )


def _build_react_agent(
    *,
    name: str,
    sys_prompt: str,
    agent_kind: str,
    tool_specs: list[ToolSpec],
    tool_context: ToolContext,
    progress_callback: Callable[..., None] | None,
    observation_collector: list[dict[str, Any]] | None = None,
    stage_tool_capture: dict[str, Any] | None = None,
) -> Any:
    try:
        from agentscope.agent import ReActAgent
        from agentscope.formatter import OpenAIChatFormatter
        from agentscope.model import OpenAIChatModel
        from agentscope.tool import Toolkit
    except Exception as exc:  # pragma: no cover - depends on optional dependency setup
        raise VLAReActAgentUnavailable(f"AgentScope ReAct dependency unavailable: {exc}") from exc

    cfg = _model_config(agent_kind)
    model = OpenAIChatModel(
        model_name=cfg.model_name,
        api_key=cfg.api_key,
        stream=False,
        client_kwargs={"base_url": cfg.base_url},
        generate_kwargs={
            "temperature": 0,
            "extra_body": {"enable_thinking": cfg.thinking},
        },
    )
    toolkit = Toolkit()
    for spec in tool_specs:
        func = build_agentscope_tool_function(
            spec,
            ctx_factory=lambda tool_context=tool_context: tool_context,
            runtime_invoke=_runtime_invoke(
                agent_name=name,
                progress_callback=progress_callback,
                observation_collector=observation_collector,
                stage_tool_capture=stage_tool_capture,
            ),
        )
        toolkit.register_tool_function(
            func,
            json_schema=build_agentscope_json_schema(spec),
        )
    agent = ReActAgent(
        name=name,
        sys_prompt=sys_prompt,
        model=model,
        formatter=OpenAIChatFormatter(),
        toolkit=toolkit,
        max_iters=20 if agent_kind == "plan" else 8,
        parallel_tool_calls=False,
    )
    agent.set_console_output_enabled(enabled=False)
    return agent


def _runtime_invoke(
    *,
    agent_name: str,
    progress_callback: Callable[..., None] | None,
    observation_collector: list[dict[str, Any]] | None,
    stage_tool_capture: dict[str, Any] | None,
) -> Callable[[str, dict[str, Any], Callable[[], dict[str, Any]]], dict[str, Any]]:
    def _invoke(
        tool_name: str,
        args_preview: dict[str, Any],
        execute: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        _emit(
            progress_callback,
            "tool_start",
            agent=agent_name,
            tool=tool_name,
            args_preview=args_preview,
        )
        payload = execute()
        _emit(
            progress_callback,
            "tool_end",
            agent=agent_name,
            tool=tool_name,
            ok=bool(payload.get("ok")),
            error_type=payload.get("error_type"),
        )
        if observation_collector is not None:
            observation_collector.append(
                build_observation(
                    observation_id=f"obs_{len(observation_collector) + 1}_{tool_name}",
                    tool=tool_name,
                    args=args_preview,
                    raw_result=_raw_result(payload),
                    extracted_facts=_raw_result(payload),
                    used_for=["plan_agent_react"],
                )
            )
        if stage_tool_capture is not None:
            stage_tool_capture["tool_args_preview"] = dict(args_preview)
            stage_tool_capture["tool_result"] = dict(payload)
        return payload

    return _invoke


def _run_agent(agent: Any, payload: Mapping[str, Any]) -> str:
    try:
        from agentscope.message import Msg
    except Exception as exc:  # pragma: no cover - depends on optional dependency setup
        raise VLAReActAgentUnavailable(f"AgentScope message dependency unavailable: {exc}") from exc

    prompt = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        reply = agent(Msg(name="user", role="user", content=prompt))
        if inspect.isawaitable(reply):
            reply = _run_awaitable(reply)
    except Exception as exc:
        raise VLAReActAgentUnavailable(f"VLA ReAct agent call failed: {exc}") from exc
    if hasattr(reply, "get_text_content"):
        text = str(reply.get_text_content() or "")
    else:
        text = str(getattr(reply, "content", "") or "")
    if not text.strip():
        raise VLAReActAgentUnavailable("VLA ReAct agent returned an empty response")
    return text


def _run_awaitable(awaitable: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)

    result: dict[str, Any] = {}

    def _target() -> None:
        try:
            result["value"] = asyncio.run(awaitable)
        except Exception as exc:  # pragma: no cover - defensive thread bridge
            result["error"] = exc

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _plan_agent_input_payload(
    *,
    user_request: str,
    scenario: str,
    user_inputs: Mapping[str, Any],
    source_docs: list[str],
    planning_notes: Mapping[str, Any],
    catalog: list[ToolCapability],
    observations: list[dict[str, Any]],
    profile_draft: Mapping[str, Any],
    plan_draft: Mapping[str, Any],
    validation_feedback: Mapping[str, Any] | None,
    repair_attempt: int,
) -> dict[str, Any]:
    return {
        "user_request": user_request,
        "scenario": scenario,
        "user_inputs": dict(user_inputs),
        "source_docs": source_docs,
        "planning_notes": dict(planning_notes),
        "tool_capability_catalog": [_plain(capability) for capability in catalog],
        "observations": observations,
        "profile_schema": NavigationVLADataProfile.model_json_schema(),
        "plan_schema": VLAWorkflowPlan.model_json_schema(),
        "profile_draft": dict(profile_draft),
        "plan_draft": dict(plan_draft),
        "validation_feedback": dict(validation_feedback or {}),
        "repair_attempt": repair_attempt,
        "remaining_repair_attempts": max(_MAX_PLAN_REPAIR_ATTEMPTS - repair_attempt, 0),
        "required_output_schema": {
            "planning_notes": "object",
            "observations": "array",
            "data_profile": "NavigationVLADataProfile object",
            "plan": "VLAWorkflowPlan object",
            "decisions": "array",
        },
    }


def _observations_from_payload(
    payload: Mapping[str, Any],
    collected_observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw = payload.get("observations") or collected_observations
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _validate_plan_agent_drafts(
    *,
    data_profile_payload: Mapping[str, Any],
    plan_payload: Mapping[str, Any],
    catalog: list[ToolCapability],
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    data_profile: NavigationVLADataProfile | None = None
    plan: VLAWorkflowPlan | None = None

    try:
        data_profile = NavigationVLADataProfile.model_validate(
            dict(data_profile_payload)
        )
    except ValidationError as exc:
        errors.append(
            {
                "target": "data_profile",
                "type": "schema_validation_failed",
                "message": str(exc),
                "details": {"errors": exc.errors()},
            }
        )
    else:
        profile_validation = validate_navigation_data_profile_model(data_profile)
        for error in profile_validation["errors"]:
            item = dict(error)
            item.setdefault("target", "data_profile")
            errors.append(item)
        warnings.extend(
            {"target": "data_profile", **dict(item)}
            for item in profile_validation["warnings"]
        )

    try:
        plan = VLAWorkflowPlan.model_validate(dict(plan_payload))
    except ValidationError as exc:
        errors.append(
            {
                "target": "plan",
                "type": "schema_validation_failed",
                "message": str(exc),
                "details": {"errors": exc.errors()},
            }
        )
    else:
        plan_validation = validate_plan(plan, catalog=catalog)
        for error in plan_validation["errors"]:
            item = dict(error)
            item.setdefault("target", "plan")
            errors.append(item)
        warnings.extend(
            {"target": "plan", **dict(item)}
            for item in plan_validation["warnings"]
        )

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "data_profile": data_profile,
        "plan": plan,
    }


def _plan_tool_specs(catalog: list[ToolCapability]) -> list[ToolSpec]:
    names = [
        capability.tool
        for capability in catalog
        if capability.plan_agent_allowed and capability.implementation_status == "available"
    ]
    specs: list[ToolSpec] = []
    for name in dict.fromkeys(names):
        try:
            specs.append(get_tool_spec(name))
        except KeyError:
            continue
    return specs


def _parse_json_object(text: str) -> dict[str, Any]:
    match = _JSON_BLOCK_RE.search(text)
    payload = match.group(1).strip() if match else text.strip()
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise VLAReActAgentUnavailable(f"VLA ReAct agent did not return valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise VLAReActAgentUnavailable("VLA ReAct agent JSON response must be an object")
    return parsed


def _plain(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _raw_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, Mapping):
        return dict(data)
    return dict(payload)


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


def _plan_sys_prompt() -> str:
    return (
        "You are VLAPlanReActAgent, a real Plan-Agent for navigation VLA data processing. "
        "Use only the provided read-only planning tools. Do not execute write, external, "
        "or long-running processing tools. Read the user request, planning notes, tool "
        "capability catalog, profile_schema, plan_schema, current drafts, validation "
        "feedback, and available observations. Call inspection tools until the data shape "
        "is clear. Then return one JSON object only with planning_notes, observations, "
        "data_profile, plan, and decisions. Fill NavigationVLADataProfile from observed "
        "facts and choose VLAWorkflowPlan stage variants from the capability catalog. "
        "When validation_feedback is present, repair only the invalid or missing fields "
        "and keep valid evidence-backed fields."
    )


def _executor_sys_prompt() -> str:
    return (
        "You are VLAExecutorReActAgent, a real Executor-Agent for one VLA workflow stage. "
        "You may call only the single tool exposed in this turn. Do not change the stage "
        "order, tool, or variant. Fill tool arguments from current_stage, data_profile, "
        "observations, previous_stage_outputs, runtime_context, tool_capability, and "
        "tool_input_schema. After the tool call, return one JSON object matching the "
        "VLAStageResult schema. Use next_action continue, retry, pause, replan, or stop."
    )


__all__ = [
    "VLAReActAgentUnavailable",
    "VLAReActPlanValidationError",
    "ensure_react_agents_available",
    "run_executor_agent_react",
    "run_plan_agent_react",
]

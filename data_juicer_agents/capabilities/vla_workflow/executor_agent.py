from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from data_juicer_agents.capabilities.vla_workflow.catalog.model import (
    ToolCapability,
    ToolVariant,
)
from data_juicer_agents.capabilities.vla_workflow.catalog.service import (
    list_tool_capabilities,
)
from data_juicer_agents.capabilities.vla_workflow.plan.model import (
    VLAWorkflowPlan,
    VLAWorkflowStage,
)
from data_juicer_agents.core.tool import (
    ToolContext,
    ToolResult,
    ToolSpec,
    get_tool_spec,
)


StageResultStatus = Literal[
    "success",
    "failed",
    "needs_user",
    "needs_replan",
    "interrupted",
]
StageNextAction = Literal["continue", "retry", "pause", "replan", "stop"]


class VLAStageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: str
    stage_kind: str
    tool: str
    variant: str
    status: StageResultStatus
    tool_args_preview: dict[str, Any] = Field(default_factory=dict)
    tool_result: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    error_type: str = ""
    next_action: StageNextAction
    summary: str = ""


class VariantArgumentConflict(ValueError):
    def __init__(
        self,
        *,
        stage_id: str,
        stage_kind: str,
        tool: str,
        variant: str,
        conflicts: list[dict[str, Any]],
    ) -> None:
        super().__init__("explicit stage arguments conflict with the planned variant")
        self.stage_id = stage_id
        self.stage_kind = stage_kind
        self.tool = tool
        self.variant = variant
        self.conflicts = conflicts


_MISSING = object()


def bind_stage_tool_args(
    *,
    current_stage: VLAWorkflowStage,
    data_profile: BaseModel | Mapping[str, Any],
    observations: list[dict[str, Any]],
    previous_stage_outputs: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
    capability: ToolCapability | None = None,
) -> dict[str, Any]:
    """Bind the current stage to one tool input without changing the plan."""

    profile_data = _to_plain_data(data_profile)
    args: dict[str, Any] = {}
    variant = _find_variant(capability, current_stage.variant) if capability else None

    if variant is not None:
        for arg_name, source_path in variant.arg_bindings.items():
            value = _resolve_binding(
                source_path,
                profile_data=profile_data,
                observations=observations,
                previous_stage_outputs=previous_stage_outputs,
                runtime_context=runtime_context,
            )
            if value is not _MISSING:
                args[arg_name] = value

    _apply_stage_defaults(
        args,
        current_stage=current_stage,
        profile_data=profile_data,
        variant=variant,
    )
    args.update(_runtime_common_args(runtime_context))
    _merge_explicit_stage_args(args, runtime_context=runtime_context, stage=current_stage)
    return args


def execute_stage(
    *,
    plan: VLAWorkflowPlan,
    current_stage: VLAWorkflowStage,
    data_profile: BaseModel | Mapping[str, Any],
    observations: list[dict[str, Any]],
    previous_stage_outputs: Mapping[str, Any],
    runtime_context: Mapping[str, Any] | None = None,
    registry: Any | None = None,
    catalog: Iterable[ToolCapability] | None = None,
    tool_context: ToolContext | None = None,
) -> VLAStageResult:
    context = dict(runtime_context or {})
    capability = _resolve_capability(plan, current_stage, catalog)
    try:
        args = bind_stage_tool_args(
            current_stage=current_stage,
            data_profile=data_profile,
            observations=observations,
            previous_stage_outputs=previous_stage_outputs,
            runtime_context=context,
            capability=capability,
        )
    except VariantArgumentConflict as exc:
        return VLAStageResult(
            stage_id=current_stage.id,
            stage_kind=current_stage.stage_kind,
            tool=current_stage.tool,
            variant=current_stage.variant,
            status="needs_replan",
            tool_args_preview={},
            tool_result={
                "ok": False,
                "action": current_stage.tool,
                "error_type": "variant_argument_conflict",
                "error_message": str(exc),
                "conflicts": exc.conflicts,
            },
            error_type="variant_argument_conflict",
            next_action="replan",
            summary="explicit stage arguments conflict with the planned variant",
        )

    try:
        spec = _get_current_tool_spec(current_stage.tool, registry)
        tool_result = spec.execute(
            tool_context or _tool_context_from_runtime(context),
            args,
        )
    except ValidationError as exc:
        tool_result = ToolResult.failure(
            summary=f"invalid arguments for {current_stage.tool}",
            error_type="invalid_arguments",
            error_message=str(exc),
            data={"validation_errors": exc.errors()},
        )
    except KeyError as exc:
        tool_result = ToolResult.failure(
            summary=str(exc),
            error_type="invalid_arguments",
            error_message=str(exc),
        )

    payload = tool_result.to_payload(action=current_stage.tool)
    status, next_action = _route_tool_result(
        current_stage=current_stage,
        tool_result=tool_result,
        payload=payload,
        capability=capability,
    )
    artifacts = _extract_artifacts(tool_result, payload)
    return VLAStageResult(
        stage_id=current_stage.id,
        stage_kind=current_stage.stage_kind,
        tool=current_stage.tool,
        variant=current_stage.variant,
        status=status,
        tool_args_preview=dict(args),
        tool_result=payload,
        artifacts=artifacts,
        error_type=str(payload.get("error_type") or tool_result.error_type or ""),
        next_action=next_action,
        summary=str(
            payload.get("message")
            or tool_result.summary
            or _default_stage_summary(current_stage, status)
        ),
    )


def _apply_stage_defaults(
    args: dict[str, Any],
    *,
    current_stage: VLAWorkflowStage,
    profile_data: Mapping[str, Any],
    variant: ToolVariant | None,
) -> None:
    stage_kind = current_stage.stage_kind
    dataset = _mapping_at(profile_data, "dataset")

    if stage_kind in {
        "inspect_raw_date",
        "prepare_raw_temp",
        "extract_and_sync",
        "list_clip_segments",
        "prepare_finish_dataset",
        "gridmap_processing",
        "validate_outputs",
    }:
        _set_if_present(args, "date", dataset.get("date"))

    if stage_kind in {
        "prepare_raw_temp",
        "extract_and_sync",
        "prepare_finish_dataset",
        "gridmap_processing",
        "validate_outputs",
    }:
        _set_if_present(args, "selected_segments", dataset.get("selected_segments"))

    if stage_kind == "extract_and_sync":
        _set_if_present(args, "query_dir", _get_path(profile_data, "sync.query_raw_dir"))
        args.setdefault("script_variant", current_stage.variant)
        return

    if stage_kind == "prepare_finish_dataset":
        scene_mode = dataset.get("scene_mode")
        if scene_mode != "unknown":
            _set_if_present(args, "scene_mode", scene_mode)
        return

    if stage_kind == "gridmap_processing":
        args.setdefault(
            "gridmap_variant",
            _stage_config_value(variant, "gridmap_variant", current_stage.variant),
        )
        return

    if stage_kind == "projection_and_trajectory":
        args.setdefault("trajectory_variant", current_stage.variant)
        args.setdefault(
            "use_gridmap",
            bool(_stage_config_value(variant, "requires_gridmap", True)),
        )
        return

    if stage_kind == "validate_outputs":
        expect_gridmap = _get_path(profile_data, "gridmap.expect_gridmap_output")
        if expect_gridmap is not _MISSING:
            args.setdefault("expect_gridmap_output", bool(expect_gridmap))


def _route_tool_result(
    *,
    current_stage: VLAWorkflowStage,
    tool_result: ToolResult,
    payload: Mapping[str, Any],
    capability: ToolCapability | None,
) -> tuple[StageResultStatus, StageNextAction]:
    error_type = str(payload.get("error_type") or tool_result.error_type or "")

    if current_stage.stage_kind == "manual_box_annotation":
        if _manual_annotation_yaml_ready(payload):
            return "success", "continue"
        if _manual_annotation_yaml_missing(payload, error_type):
            return "needs_user", "pause"

    if bool(payload.get("ok", tool_result.ok)):
        return "success", "continue"

    if error_type == "interrupted":
        return "interrupted", "stop"

    if error_type in _recoverable_error_types(capability, current_stage.variant):
        return "failed", "retry"

    if error_type in {"invalid_arguments", "variant_argument_conflict"}:
        return "needs_replan", "replan"

    return "failed", "stop"


def _manual_annotation_yaml_ready(payload: Mapping[str, Any]) -> bool:
    yaml_paths = payload.get("yaml_paths")
    missing = payload.get("missing_yaml_clips")
    if isinstance(yaml_paths, list):
        return bool(yaml_paths) and not missing
    clips = payload.get("clips")
    if isinstance(clips, dict) and clips:
        return all(int((item or {}).get("yaml_count") or 0) > 0 for item in clips.values())
    return bool(payload.get("annotation_yaml") or payload.get("annotation_yaml_path"))


def _manual_annotation_yaml_missing(
    payload: Mapping[str, Any],
    error_type: str,
) -> bool:
    if error_type == "missing_annotation_yaml":
        return True
    missing = payload.get("missing_yaml_clips")
    if isinstance(missing, list) and missing:
        return True
    return bool(payload.get("ok")) and payload.get("yaml_paths") == []


def _resolve_binding(
    source_path: str,
    *,
    profile_data: Mapping[str, Any],
    observations: list[dict[str, Any]],
    previous_stage_outputs: Mapping[str, Any],
    runtime_context: Mapping[str, Any],
) -> Any:
    source = str(source_path or "").strip()
    if not source:
        return _MISSING

    roots: list[tuple[str, Any]] = [
        ("data_profile.", profile_data),
        ("profile.", profile_data),
        ("runtime_context.", runtime_context),
        ("runtime.", runtime_context),
        ("previous_stage_outputs.", previous_stage_outputs),
        ("previous.", previous_stage_outputs),
        ("observations.", observations),
    ]
    for prefix, root in roots:
        if source.startswith(prefix):
            return _get_path(root, source[len(prefix) :])
    return _get_path(profile_data, source)


def _get_path(root: Any, path: str) -> Any:
    current = root
    for part in str(path or "").split("."):
        if not part:
            continue
        if isinstance(current, BaseModel):
            current = current.model_dump()
        if isinstance(current, Mapping):
            if part not in current:
                return _MISSING
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return _MISSING
            current = current[index]
            continue
        return _MISSING
    return current


def _mapping_at(root: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    value = _get_path(root, path)
    return value if isinstance(value, Mapping) else {}


def _to_plain_data(value: BaseModel | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, BaseModel):
        return value.model_dump()
    return dict(value)


def _set_if_present(args: dict[str, Any], key: str, value: Any) -> None:
    if value is not _MISSING and value not in (None, ""):
        args.setdefault(key, value)


def _stage_config_value(
    variant: ToolVariant | None,
    key: str,
    default: Any = _MISSING,
) -> Any:
    if variant is None:
        return default
    return variant.stage_config.get(key, default)


def _explicit_stage_args(
    runtime_context: Mapping[str, Any],
    stage: VLAWorkflowStage,
) -> dict[str, Any]:
    explicit: dict[str, Any] = {}
    for group_name in ("stage_args", "tool_args", "overrides"):
        group = runtime_context.get(group_name)
        if not isinstance(group, Mapping):
            continue
        for key in (stage.id, stage.stage_kind, stage.tool):
            values = group.get(key)
            if isinstance(values, Mapping):
                explicit.update(values)
    return explicit


def _merge_explicit_stage_args(
    args: dict[str, Any],
    *,
    runtime_context: Mapping[str, Any],
    stage: VLAWorkflowStage,
) -> None:
    explicit = _explicit_stage_args(runtime_context, stage)
    conflicts = _variant_argument_conflicts(args, explicit, stage)
    if conflicts:
        raise VariantArgumentConflict(
            stage_id=stage.id,
            stage_kind=stage.stage_kind,
            tool=stage.tool,
            variant=stage.variant,
            conflicts=conflicts,
        )
    args.update(explicit)


def _variant_argument_conflicts(
    planned_args: Mapping[str, Any],
    explicit_args: Mapping[str, Any],
    stage: VLAWorkflowStage,
) -> list[dict[str, Any]]:
    protected = _protected_variant_args(stage)
    conflicts: list[dict[str, Any]] = []
    for key, expected in protected.items():
        if key not in explicit_args:
            continue
        actual = explicit_args[key]
        if not _same_variant_value(actual, expected):
            conflicts.append(
                {
                    "arg": key,
                    "expected": expected,
                    "actual": actual,
                    "stage_id": stage.id,
                    "stage_kind": stage.stage_kind,
                    "variant": stage.variant,
                }
            )
    return conflicts


def _protected_variant_args(stage: VLAWorkflowStage) -> dict[str, Any]:
    if stage.stage_kind == "extract_and_sync":
        return {"script_variant": stage.variant}
    if stage.stage_kind == "gridmap_processing":
        return {"gridmap_variant": stage.variant}
    if stage.stage_kind == "projection_and_trajectory":
        return {"trajectory_variant": stage.variant, "use_gridmap": True}
    return {}


def _same_variant_value(actual: Any, expected: Any) -> bool:
    if isinstance(expected, bool):
        return actual is expected
    return str(actual) == str(expected)


def _runtime_common_args(runtime_context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: runtime_context[key]
        for key in ("dry_run", "run_id", "log_dir")
        if key in runtime_context
    }


def _resolve_capability(
    plan: VLAWorkflowPlan,
    stage: VLAWorkflowStage,
    catalog: Iterable[ToolCapability] | None,
) -> ToolCapability | None:
    resolved_catalog = list(catalog) if catalog is not None else list_tool_capabilities(
        scenario=plan.scenario,
        tool=stage.tool,
    )
    for capability in resolved_catalog:
        if capability.tool == stage.tool and capability.stage_kind == stage.stage_kind:
            return capability
    return None


def _find_variant(
    capability: ToolCapability | None,
    variant_id: str,
) -> ToolVariant | None:
    if capability is None:
        return None
    for variant in capability.variants:
        if variant.id == variant_id:
            return variant
    return None


def _recoverable_error_types(
    capability: ToolCapability | None,
    variant_id: str,
) -> set[str]:
    variant = _find_variant(capability, variant_id)
    if variant is None:
        return set()
    result: set[str] = set()
    for item in variant.recoverable_errors:
        if isinstance(item, str):
            result.add(item)
        elif isinstance(item, Mapping):
            error_type = str(item.get("type") or "")
            if error_type:
                result.add(error_type)
    return result


def _get_current_tool_spec(tool_name: str, registry: Any | None) -> ToolSpec:
    if registry is None:
        return get_tool_spec(tool_name)
    if isinstance(registry, Mapping):
        return registry[tool_name]
    if hasattr(registry, "get"):
        return registry.get(tool_name)
    raise TypeError("registry must be a mapping, ToolRegistry-like object, or None")


def _tool_context_from_runtime(runtime_context: Mapping[str, Any]) -> ToolContext:
    env = runtime_context.get("env") if isinstance(runtime_context.get("env"), Mapping) else {}
    return ToolContext(
        working_dir=str(runtime_context.get("working_dir") or "./.djx"),
        env={str(key): str(value) for key, value in dict(env).items()},
        artifacts_dir=(
            str(runtime_context["artifacts_dir"])
            if runtime_context.get("artifacts_dir") is not None
            else None
        ),
        runtime_values=dict(runtime_context),
    )


def _extract_artifacts(
    tool_result: ToolResult,
    payload: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if isinstance(payload.get("artifacts"), list):
        return [dict(item) for item in payload["artifacts"] if isinstance(item, Mapping)]
    return [artifact.to_dict() for artifact in tool_result.artifacts]


def _default_stage_summary(stage: VLAWorkflowStage, status: str) -> str:
    return f"{stage.stage_kind} {status}"


__all__ = [
    "StageNextAction",
    "StageResultStatus",
    "VariantArgumentConflict",
    "VLAStageResult",
    "bind_stage_tool_args",
    "execute_stage",
]

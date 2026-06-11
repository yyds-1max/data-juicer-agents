from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from data_juicer_agents.capabilities.vla_workflow.catalog.model import (
    ToolCapability,
    ToolVariant,
)
from data_juicer_agents.capabilities.vla_workflow.executor_agent import (
    bind_stage_tool_args,
    execute_stage,
)
from data_juicer_agents.capabilities.vla_workflow.plan.model import (
    VLAWorkflowPlan,
    VLAWorkflowStage,
)
from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationCalibrationProfile,
    NavigationDatasetProfile,
    NavigationGridmapProfile,
    NavigationLocalizationProfile,
    NavigationProcessingState,
    NavigationSyncProfile,
    NavigationTopicsProfile,
    NavigationVLADataProfile,
    StageVariantDecision,
)
from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec


class AnyInput(BaseModel):
    model_config = ConfigDict(extra="allow")


class RecordingRegistry:
    def __init__(self, specs: dict[str, ToolSpec]) -> None:
        self.specs = specs
        self.requested: list[str] = []

    def get(self, name: str) -> ToolSpec:
        self.requested.append(name)
        return self.specs[name]


def _spec(
    name: str,
    *,
    result: ToolResult | None = None,
    calls: list[dict[str, Any]] | None = None,
) -> ToolSpec:
    def _executor(ctx: ToolContext, args: BaseModel) -> ToolResult:
        if calls is not None:
            calls.append(args.model_dump())
        return result or ToolResult.success(summary=f"{name} ok", data={"ok": True})

    return ToolSpec(
        name=name,
        description=f"fake {name}",
        input_model=AnyInput,
        output_model=None,
        executor=_executor,
        tags=("vla",),
        effects="execute",
    )


def _stage(
    stage_kind: str,
    tool: str,
    variant: str,
    *,
    effects: str = "execute",
) -> VLAWorkflowStage:
    return VLAWorkflowStage(
        id=stage_kind,
        stage_kind=stage_kind,
        tool=tool,
        variant=variant,
        effects=effects,
    )


def _plan(stages: list[VLAWorkflowStage]) -> VLAWorkflowPlan:
    return VLAWorkflowPlan(
        plan_id="vla_plan_test",
        scenario="navigation_vla",
        status="pending",
        planning_notes_ref="planning_notes.json",
        observations_ref="observations.json",
        data_profile_ref="data_profile.json",
        active_stages=stages,
    )


def _profile() -> NavigationVLADataProfile:
    profile = NavigationVLADataProfile(
        dataset=NavigationDatasetProfile(
            date="20270515",
            raw_root="/data/raw",
            raw_date_dir="/data/raw/20270515",
            raw_work_dir="/data/raw/20270515_temp",
            clip_root="/data/clip",
            finish_root="/data/finish",
            trajectory_root="/srv/trajectory",
            scene_mode="out",
            selected_segments=["seg_a", "seg_b"],
        ),
        topics=NavigationTopicsProfile(
            topic_schema="u_legacy_topics",
            required_roles_present=True,
        ),
        sync=NavigationSyncProfile(
            query_raw_dir="lidar_points",
            query_canonical_dir="r32_rslidar_points",
        ),
        processing_state=NavigationProcessingState(),
        localization=NavigationLocalizationProfile(source="odom"),
        calibration=NavigationCalibrationProfile(
            sensor_params_dir="/srv/params/go2w",
            sensor_params_status="present",
        ),
        gridmap=NavigationGridmapProfile(
            gridmap_source="generated_from_pointcloud",
            requires_gridmap_processing=True,
            expect_gridmap_output=True,
        ),
    )
    profile.stage_variants = {
        "extract_and_sync": StageVariantDecision(variant="u_legacy_topics"),
        "gridmap_processing": StageVariantDecision(variant="pointcloud_to_gridmap"),
        "projection_and_trajectory": StageVariantDecision(variant="cjl_with_gridmap"),
        "validate_outputs": StageVariantDecision(variant="expect_gridmap"),
    }
    return profile


def _capability(tool: str, stage_kind: str, variants: list[ToolVariant]) -> ToolCapability:
    return ToolCapability(
        tool=tool,
        scenario="navigation_vla",
        stage_kind=stage_kind,
        effects="execute",
        implementation_status="available",
        supports_dry_run=True,
        plan_agent_allowed=False,
        executor_agent_allowed=True,
        variants=variants,
    )


def test_extract_and_sync_stage_binds_query_dir_and_script_variant():
    stage = _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics")
    capability = _capability(
        "vla_extract_and_sync",
        "extract_and_sync",
        [
            ToolVariant(
                id="u_legacy_topics",
                status="available",
                arg_bindings={
                    "date": "dataset.date",
                    "selected_segments": "dataset.selected_segments",
                    "query_dir": "sync.query_raw_dir",
                    "script_variant": "stage_variants.extract_and_sync.variant",
                },
            )
        ],
    )

    args = bind_stage_tool_args(
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={},
        capability=capability,
    )

    assert args["query_dir"] == "lidar_points"
    assert args["script_variant"] == "u_legacy_topics"


def test_gridmap_processing_binds_variant_without_default_server_paths():
    stage = _stage("gridmap_processing", "vla_prepare_gridmap", "pointcloud_to_gridmap")

    args = bind_stage_tool_args(
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={},
        capability=None,
    )

    assert args["gridmap_variant"] == "pointcloud_to_gridmap"
    assert "clip_root" not in args
    assert "finish_root" not in args
    assert "trajectory_root" not in args
    assert "generator_script" not in args


def test_projection_and_validation_bind_stage_specific_flags():
    profile = _profile()

    projection_args = bind_stage_tool_args(
        current_stage=_stage(
            "projection_and_trajectory",
            "vla_run_projection_and_trajectory",
            "cjl_with_gridmap",
        ),
        data_profile=profile,
        observations=[],
        previous_stage_outputs={},
        runtime_context={
            "stage_args": {
                "projection_and_trajectory": {
                    "save_path": "/data/finish/20270515",
                    "save_path_temp": "/data/finish/20270515_temp",
                }
            }
        },
        capability=None,
    )
    validation_args = bind_stage_tool_args(
        current_stage=_stage("validate_outputs", "vla_validate_outputs", "expect_gridmap"),
        data_profile=profile,
        observations=[],
        previous_stage_outputs={},
        runtime_context={},
        capability=None,
    )

    assert projection_args["trajectory_variant"] == "cjl_with_gridmap"
    assert projection_args["use_gridmap"] is True
    assert validation_args["expect_gridmap_output"] is True


def test_executor_only_fetches_and_calls_current_stage_tool():
    calls: list[dict[str, Any]] = []
    current = _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics")
    other = _stage("run_tracking", "vla_run_tracking", "default")
    registry = RecordingRegistry(
        {
            "vla_extract_and_sync": _spec("vla_extract_and_sync", calls=calls),
            "vla_run_tracking": _spec("vla_run_tracking"),
        }
    )

    result = execute_stage(
        plan=_plan([current, other]),
        current_stage=current,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={},
        registry=registry,
        catalog=[
            _capability(
                "vla_extract_and_sync",
                "extract_and_sync",
                [
                    ToolVariant(
                        id="u_legacy_topics",
                        status="available",
                        arg_bindings={"date": "dataset.date"},
                    )
                ],
            )
        ],
    )

    assert result.status == "success"
    assert result.next_action == "continue"
    assert registry.requested == ["vla_extract_and_sync"]
    assert calls[0]["date"] == "20270515"
    assert calls[0]["script_variant"] == "u_legacy_topics"


def test_recoverable_error_routes_to_retry():
    stage = _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics")
    result = execute_stage(
        plan=_plan([stage]),
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={},
        registry={
            "vla_extract_and_sync": _spec(
                "vla_extract_and_sync",
                result=ToolResult.failure(
                    summary="missing segments",
                    error_type="missing_raw_segments",
                ),
            )
        },
        catalog=[
            _capability(
                "vla_extract_and_sync",
                "extract_and_sync",
                [
                    ToolVariant(
                        id="u_legacy_topics",
                        status="available",
                        recoverable_errors=[{"type": "missing_raw_segments"}],
                    )
                ],
            )
        ],
    )

    assert result.status == "failed"
    assert result.next_action == "retry"


def test_invalid_arguments_routes_to_replan():
    stage = _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics")

    result = execute_stage(
        plan=_plan([stage]),
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={},
        registry={
            "vla_extract_and_sync": _spec(
                "vla_extract_and_sync",
                result=ToolResult.failure(
                    summary="bad args",
                    error_type="invalid_arguments",
                ),
            )
        },
        catalog=[],
    )

    assert result.status == "needs_replan"
    assert result.next_action == "replan"


def test_manual_annotation_missing_yaml_pauses_for_user():
    stage = _stage(
        "manual_box_annotation",
        "vla_run_manual_box_annotation",
        "default",
    )

    result = execute_stage(
        plan=_plan([stage]),
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={
            "stage_args": {
                "manual_box_annotation": {
                    "save_path_temp": "/data/finish/20270515_temp",
                }
            }
        },
        registry={
            "vla_run_manual_box_annotation": _spec(
                "vla_run_manual_box_annotation",
                result=ToolResult.success(
                    summary="checkpoint inspected",
                    data={"ok": True, "yaml_paths": [], "missing_yaml_clips": ["seg_a"]},
                ),
            )
        },
        catalog=[],
    )

    assert result.status == "needs_user"
    assert result.next_action == "pause"


def test_runtime_override_cannot_change_extract_and_sync_variant():
    calls: list[dict[str, Any]] = []
    stage = _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics")

    result = execute_stage(
        plan=_plan([stage]),
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={
            "stage_args": {
                "extract_and_sync": {"script_variant": "go2w_current_topics"}
            }
        },
        registry={"vla_extract_and_sync": _spec("vla_extract_and_sync", calls=calls)},
        catalog=[],
    )

    assert result.status == "needs_replan"
    assert result.next_action == "replan"
    assert result.error_type == "variant_argument_conflict"
    assert calls == []


def test_runtime_override_may_repeat_planned_variant_values():
    calls: list[dict[str, Any]] = []
    stage = _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics")

    result = execute_stage(
        plan=_plan([stage]),
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={
            "stage_args": {
                "extract_and_sync": {"script_variant": "u_legacy_topics"}
            }
        },
        registry={"vla_extract_and_sync": _spec("vla_extract_and_sync", calls=calls)},
        catalog=[],
    )

    assert result.status == "success"
    assert result.next_action == "continue"
    assert calls[0]["script_variant"] == "u_legacy_topics"


def test_runtime_override_cannot_change_gridmap_processing_variant():
    calls: list[dict[str, Any]] = []
    stage = _stage("gridmap_processing", "vla_prepare_gridmap", "pointcloud_to_gridmap")

    result = execute_stage(
        plan=_plan([stage]),
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={
            "stage_args": {
                "gridmap_processing": {"gridmap_variant": "copy_existing_artifact"}
            }
        },
        registry={"vla_prepare_gridmap": _spec("vla_prepare_gridmap", calls=calls)},
        catalog=[],
    )

    assert result.status == "needs_replan"
    assert result.next_action == "replan"
    assert result.error_type == "variant_argument_conflict"
    assert calls == []


def test_runtime_override_cannot_change_projection_variant_or_gridmap_semantics():
    calls: list[dict[str, Any]] = []
    stage = _stage(
        "projection_and_trajectory",
        "vla_run_projection_and_trajectory",
        "cjl_with_gridmap",
    )

    result = execute_stage(
        plan=_plan([stage]),
        current_stage=stage,
        data_profile=_profile(),
        observations=[],
        previous_stage_outputs={},
        runtime_context={
            "stage_args": {
                "projection_and_trajectory": {
                    "save_path": "/data/finish/20270515",
                    "save_path_temp": "/data/finish/20270515_temp",
                    "trajectory_variant": "cjl_0525_with_gridmap",
                    "use_gridmap": False,
                }
            }
        },
        registry={
            "vla_run_projection_and_trajectory": _spec(
                "vla_run_projection_and_trajectory",
                calls=calls,
            )
        },
        catalog=[],
    )

    assert result.status == "needs_replan"
    assert result.next_action == "replan"
    assert result.error_type == "variant_argument_conflict"
    assert calls == []

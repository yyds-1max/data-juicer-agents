from __future__ import annotations

from typing import Any

from .model import CapabilityStatus, ToolCapability, ToolEffect, ToolVariant


def _variant(
    variant_id: str,
    *,
    status: CapabilityStatus = "available",
    selectors: dict[str, list[str]] | None = None,
    arg_bindings: dict[str, str] | None = None,
    preconditions: list[dict[str, Any]] | None = None,
    expected_artifacts: list[dict[str, Any]] | None = None,
    recoverable_errors: list[dict[str, Any]] | None = None,
    stage_config: dict[str, Any] | None = None,
) -> ToolVariant:
    return ToolVariant(
        id=variant_id,
        status=status,
        selectors=selectors or {},
        arg_bindings=arg_bindings or {},
        preconditions=preconditions or [],
        expected_artifacts=expected_artifacts or [],
        recoverable_errors=recoverable_errors or [],
        stage_config=stage_config or {},
    )


def _capability(
    *,
    tool: str,
    stage_kind: str,
    effects: ToolEffect,
    variants: list[ToolVariant],
    implementation_status: CapabilityStatus = "available",
    supports_dry_run: bool = False,
    plan_agent_allowed: bool | None = None,
    executor_agent_allowed: bool | None = None,
) -> ToolCapability:
    if plan_agent_allowed is None:
        plan_agent_allowed = effects == "read"
    if executor_agent_allowed is None:
        executor_agent_allowed = effects != "read"
    return ToolCapability(
        tool=tool,
        scenario="navigation_vla",
        stage_kind=stage_kind,
        effects=effects,
        implementation_status=implementation_status,
        supports_dry_run=supports_dry_run,
        plan_agent_allowed=plan_agent_allowed,
        executor_agent_allowed=executor_agent_allowed,
        variants=variants,
    )


NAVIGATION_TOOL_CAPABILITIES: list[ToolCapability] = [
    _capability(
        tool="vla_check_runtime",
        stage_kind="check_runtime",
        effects="read",
        supports_dry_run=True,
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_inspect_raw_date",
        stage_kind="inspect_raw_date",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_inspect_raw_layout",
        stage_kind="inspect_raw_layout",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_inspect_rosbag_metadata",
        stage_kind="inspect_rosbag_metadata",
        effects="read",
        variants=[_variant("metadata_yaml")],
    ),
    _capability(
        tool="vla_classify_navigation_topic_schema",
        stage_kind="classify_topic_schema",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_infer_sync_policy",
        stage_kind="infer_sync_policy",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_inspect_datatoolbox_variants",
        stage_kind="inspect_datatoolbox_variants",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_inspect_processing_state",
        stage_kind="inspect_processing_state",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_inspect_calibration_assets",
        stage_kind="inspect_calibration_assets",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_infer_localization_policy",
        stage_kind="infer_localization_policy",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_inspect_gridmap_artifacts",
        stage_kind="inspect_gridmap_artifacts",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_inspect_trajectory_script_variants",
        stage_kind="inspect_trajectory_script_variants",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_list_tool_capability_catalog",
        stage_kind="list_tool_capability_catalog",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_validate_navigation_data_profile",
        stage_kind="validate_navigation_data_profile",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_prepare_raw_temp",
        stage_kind="prepare_raw_temp",
        effects="write",
        supports_dry_run=True,
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_extract_and_sync",
        stage_kind="extract_and_sync",
        effects="execute",
        supports_dry_run=True,
        variants=[
            _variant(
                "u_legacy_topics",
                selectors={"topic_schema": ["u_legacy_topics"]},
                arg_bindings={
                    "date": "dataset.date",
                    "selected_segments": "dataset.selected_segments",
                    "raw_root": "dataset.raw_root",
                    "clip_root": "dataset.clip_root",
                    "query_dir": "sync.query_raw_dir",
                    "script_variant": "stage_variants.extract_and_sync.variant",
                },
                expected_artifacts=[
                    {
                        "kind": "directory",
                        "path_template": "{clip_root}/{date}/{segment}/sync_data",
                        "required": True,
                    }
                ],
                recoverable_errors=[
                    {
                        "type": "missing_raw_segments",
                        "suggested_action": "rerun_prepare_raw_temp_or_reselect_segments",
                    }
                ],
                stage_config={
                    "topic_schema_support": ["u_legacy_topics"],
                    "supports_custom_topic_mapping": False,
                    "script_variant": "u_legacy_topics",
                },
            ),
            _variant(
                "go2w_current_topics",
                selectors={"topic_schema": ["go2w_current_topics"]},
                arg_bindings={
                    "date": "dataset.date",
                    "selected_segments": "dataset.selected_segments",
                    "raw_root": "dataset.raw_root",
                    "clip_root": "dataset.clip_root",
                    "query_dir": "sync.query_raw_dir",
                    "script_variant": "stage_variants.extract_and_sync.variant",
                },
                stage_config={
                    "topic_schema_support": ["go2w_current_topics"],
                    "supports_custom_topic_mapping": False,
                    "script_variant": "go2w_current_topics",
                },
            ),
            _variant(
                "custom_topic_mapping",
                status="placeholder",
                selectors={"topic_schema": ["custom_topics"]},
                stage_config={"supports_custom_topic_mapping": True},
            ),
        ],
    ),
    _capability(
        tool="vla_list_clip_segments",
        stage_kind="list_clip_segments",
        effects="read",
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_prepare_finish_dataset",
        stage_kind="prepare_finish_dataset",
        effects="write",
        supports_dry_run=True,
        variants=[
            _variant(
                "explicit_sensor_params",
                arg_bindings={
                    "date": "dataset.date",
                    "selected_segments": "dataset.selected_segments",
                    "sensor_params_dir": "calibration.sensor_params_dir",
                },
                expected_artifacts=[
                    {
                        "kind": "directory",
                        "path_template": "{finish_root}/{date}_temp/samples/{date}",
                        "required": True,
                    }
                ],
                stage_config={"sensor_params_policy": "explicit_path"},
            )
        ],
    ),
    _capability(
        tool="vla_build_noobscenes_inputs",
        stage_kind="build_noobscenes_inputs",
        effects="execute",
        supports_dry_run=True,
        variants=[
            _variant(
                "odom_convert_resize",
                selectors={"localization_source": ["odom"]},
                stage_config={"requires_odom_convert": True},
            ),
            _variant(
                "ins_native",
                status="planned",
                selectors={"localization_source": ["ins"]},
                stage_config={"requires_odom_convert": False},
            ),
            _variant(
                "indoor_cp_ins",
                status="planned",
                selectors={"localization_source": ["generated_ins"]},
                stage_config={"requires_indoor_ins_generation": True},
            ),
        ],
    ),
    _capability(
        tool="vla_run_manual_box_annotation",
        stage_kind="manual_box_annotation",
        effects="execute",
        supports_dry_run=True,
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_run_tracking",
        stage_kind="run_tracking",
        effects="execute",
        supports_dry_run=True,
        variants=[_variant("default")],
    ),
    _capability(
        tool="vla_prepare_gridmap",
        stage_kind="gridmap_processing",
        effects="execute",
        supports_dry_run=True,
        variants=[
            _variant(
                "copy_existing_artifact",
                selectors={
                    "gridmap_source": [
                        "raw_topic",
                        "existing_gridmap_artifact",
                    ]
                },
                expected_artifacts=[
                    {
                        "kind": "directory",
                        "path_template": "{finish_root}/{date}_temp/samples/{date}/{segment}/grid_map",
                        "required": True,
                    }
                ],
                stage_config={
                    "gridmap_variant": "copy_existing_artifact",
                    "applies_cp_gridmap_transform": True,
                },
            ),
            _variant(
                "pointcloud_to_gridmap",
                selectors={"gridmap_source": ["generated_from_pointcloud"]},
                expected_artifacts=[
                    {
                        "kind": "directory",
                        "path_template": "{finish_root}/{date}_temp/samples/{date}/{segment}/grid_map",
                        "required": True,
                    }
                ],
                stage_config={
                    "gridmap_variant": "pointcloud_to_gridmap",
                    "requires_pointcloud_pcd": True,
                    "applies_cp_gridmap_transform": True,
                },
            ),
        ],
    ),
    _capability(
        tool="vla_run_projection_and_trajectory",
        stage_kind="projection_and_trajectory",
        effects="execute",
        supports_dry_run=True,
        variants=[
            _variant(
                "cjl_with_gridmap",
                selectors={"trajectory_variant": ["cjl_with_gridmap"]},
                preconditions=[
                    {"type": "gridmap_ready", "path": "gridmap.projection_input"}
                ],
                stage_config={
                    "trajectory_script": "2_othermethod_cjl.py",
                    "move_script": "3_move_dir.py",
                    "requires_gridmap": True,
                },
            ),
            _variant(
                "cjl_0525_with_gridmap",
                selectors={"trajectory_variant": ["cjl_0525_with_gridmap"]},
                preconditions=[
                    {"type": "gridmap_ready", "path": "gridmap.projection_input"}
                ],
                stage_config={
                    "trajectory_script": "2_othermethod_cjl_0525.py",
                    "move_script": "3_move_dir.py",
                    "requires_gridmap": True,
                },
            ),
        ],
    ),
    _capability(
        tool="vla_validate_outputs",
        stage_kind="validate_outputs",
        effects="read",
        variants=[
            _variant(
                "expect_gridmap",
                selectors={"expect_gridmap_output": ["true"]},
                stage_config={"expect_gridmap_output": True},
            )
        ],
    ),
]


__all__ = ["NAVIGATION_TOOL_CAPABILITIES"]

from __future__ import annotations

import json
from datetime import datetime, timezone

from data_juicer_agents.capabilities.vla_workflow.persistence import (
    append_observation,
    build_workflow_run_dir,
    load_workflow_artifacts,
    make_workflow_run_id,
    save_data_profile,
    save_planning_notes,
    save_workflow_plan,
)
from data_juicer_agents.capabilities.vla_workflow.catalog.navigation import (
    NAVIGATION_TOOL_CAPABILITIES,
)
from data_juicer_agents.capabilities.vla_workflow.plan_agent import (
    build_observation,
    build_planning_notes,
    deterministic_plan_vla_workflow,
)
from data_juicer_agents.core.tool import ToolContext


def _copy_catalog(*, pointcloud_status: str = "available"):
    catalog = [item.model_copy(deep=True) for item in NAVIGATION_TOOL_CAPABILITIES]
    for capability in catalog:
        if capability.tool != "vla_prepare_gridmap":
            continue
        capability.variants = [
            variant.model_copy(update={"status": pointcloud_status}, deep=True)
            if variant.id == "pointcloud_to_gridmap"
            else variant
            for variant in capability.variants
        ]
    return catalog


def _topics(topic_schema: str):
    if topic_schema == "go2w_current_topics":
        return [
            {
                "name": "/cam_video4/csi_cam/image_raw/compressed",
                "type": "sensor_msgs/msg/CompressedImage",
                "role": "front_fisheye_image",
                "canonical_dir": "fisheye_front",
            },
            {
                "name": "/rs32_lidar_points",
                "type": "sensor_msgs/msg/PointCloud2",
                "role": "lidar",
                "canonical_dir": "r32_rslidar_points",
            },
            {
                "name": "/sport_odom",
                "type": "nav_msgs/msg/Odometry",
                "role": "localization_odom",
                "canonical_dir": "odom",
            },
        ]
    return [
        {
            "name": "/cam_video5/csi_cam/image_raw/compressed",
            "type": "sensor_msgs/msg/CompressedImage",
            "role": "front_fisheye_image",
            "canonical_dir": "fisheye_front",
        },
        {
            "name": "/lidar_points",
            "type": "sensor_msgs/msg/PointCloud2",
            "role": "lidar",
            "canonical_dir": "r32_rslidar_points",
        },
        {
            "name": "/utlidar/robot_odom_systime",
            "type": "nav_msgs/msg/Odometry",
            "role": "localization_odom",
            "canonical_dir": "odom",
        },
    ]


def _observations(
    *,
    date: str = "20270515",
    topic_schema: str = "u_legacy_topics",
    gridmap_source: str = "existing_gridmap_artifact",
    projection_ready: bool = False,
):
    query_raw_dir = "rs32_lidar_points" if topic_schema == "go2w_current_topics" else "lidar_points"
    topics = _topics(topic_schema)
    return [
        build_observation(
            observation_id="obs_raw_layout",
            tool="vla_inspect_raw_layout",
            raw_result={
                "date": date,
                "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
                "raw_date_dir": f"/media/heying/hy_data1/VLADatasets/raw_data/{date}",
                "raw_temp_dir": f"/media/heying/hy_data1/VLADatasets/raw_data/{date}_temp",
                "segments": [
                    {
                        "name": "segment_a",
                        "path": f"/media/heying/hy_data1/VLADatasets/raw_data/{date}/segment_a",
                        "has_db3": True,
                        "has_metadata_yaml": True,
                        "db3_files": ["segment_a_0.db3"],
                    }
                ],
                "processing_state": {"has_raw_temp": False},
            },
        ),
        build_observation(
            observation_id="obs_metadata",
            tool="vla_inspect_rosbag_metadata",
            raw_result={"topics": topics},
        ),
        build_observation(
            observation_id="obs_topic_schema",
            tool="vla_classify_navigation_topic_schema",
            raw_result={
                "topics": topics,
                "topic_schema": topic_schema,
                "topic_mapping_variant": (
                    "cam4_rs32_sport_odom"
                    if topic_schema == "go2w_current_topics"
                    else "cam5_lidar_points_utlidar_odom"
                ),
                "required_roles_present": True,
                "missing_required_roles": [],
            },
        ),
        build_observation(
            observation_id="obs_sync",
            tool="vla_infer_sync_policy",
            raw_result={
                "query_raw_dir": query_raw_dir,
                "query_canonical_dir": "r32_rslidar_points",
            },
        ),
        build_observation(
            observation_id="obs_processing",
            tool="vla_inspect_processing_state",
            raw_result={"has_sync_data": False, "sync_data_segments": []},
        ),
        build_observation(
            observation_id="obs_localization",
            tool="vla_infer_localization_policy",
            raw_result={
                "source": "odom",
                "canonical_output": "Ins_compatible_odom",
                "requires_odom_convert": True,
                "requires_cp_ins": False,
            },
        ),
        build_observation(
            observation_id="obs_calibration",
            tool="vla_inspect_calibration_assets",
            raw_result={
                "trajectory_root": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01",
                "recommended_sensor_params_dir": (
                    "/media/heying/hy_data1/Trajectory_visualization/"
                    "Object_location_gh_v3_fisheye_five_U_add_SF_01/"
                    "NoobScenes/params/20260529_go2w/sensors"
                    if topic_schema == "go2w_current_topics"
                    else "/media/heying/hy_data1/Trajectory_visualization/"
                    "Object_location_gh_v3_fisheye_five_U_add_SF_01/"
                    "NoobScenes/params/20260409_U/sensors"
                ),
                "sensor_params_status": "present",
            },
        ),
        build_observation(
            observation_id="obs_gridmap",
            tool="vla_inspect_gridmap_artifacts",
            raw_result={
                "raw_gridmap_topic_present": False,
                "gridmap_source": gridmap_source,
                "available_gridmap_artifacts": (
                    ["/clip/sync/grid_map"]
                    if gridmap_source == "existing_gridmap_artifact"
                    else []
                ),
                "artifact_locations": (
                    ["finish_temp_samples"] if projection_ready else ["clip_sync"]
                ),
                "projection_input_gridmap_ready": projection_ready,
            },
        ),
    ]


def _run_plan(
    *,
    date: str = "20270515",
    topic_schema: str = "u_legacy_topics",
    gridmap_source: str = "existing_gridmap_artifact",
    projection_ready: bool = False,
    pointcloud_status: str = "available",
):
    return deterministic_plan_vla_workflow(
        user_inputs={
            "scenario": "navigation_vla",
            "date": date,
            "clip_root": "/media/heying/hy_data1/VLADatasets/clip_data",
            "finish_root": "/media/heying/hy_data1/VLADatasets/finish_data",
            "scene_mode": "out",
        },
        observations=_observations(
            date=date,
            topic_schema=topic_schema,
            gridmap_source=gridmap_source,
            projection_ready=projection_ready,
        ),
        catalog=_copy_catalog(pointcloud_status=pointcloud_status),
    )


def _stage_by_kind(plan, stage_kind: str):
    return {stage.stage_kind: stage for stage in plan.active_stages}[stage_kind]


def test_workflow_persistence_writes_and_loads_planning_artifacts(tmp_path):
    run_dir = tmp_path / "runs" / "20270605" / "vla_navigation_vla_20270605_20260610120000"

    planning_notes = {
        "notes_id": "notes_20270605_navigation_001",
        "scenario": "navigation_vla",
        "source_docs": ["navigation_vla.md"],
        "status": "need_inspection",
    }
    data_profile = {
        "schema_version": 1,
        "scenario": "navigation_vla",
        "dataset": {"date": "20270605"},
    }
    plan = {
        "plan_id": "vla_plan_20270605_001",
        "scenario": "navigation_vla",
        "status": "pending",
        "active_stages": [],
    }

    planning_path = save_planning_notes(run_dir, planning_notes)
    first_observation_path = append_observation(
        run_dir,
        {
            "observation_id": "obs_001",
            "tool": "vla_inspect_ros2_topics",
            "raw_result": {"ok": True},
            "extracted_facts": {"topic_schema": "custom_topics"},
        },
    )
    second_observation_path = append_observation(
        run_dir,
        {
            "observation_id": "obs_002",
            "tool": "vla_inspect_gridmap_artifacts",
            "raw_result": {"ok": True},
            "extracted_facts": {"has_gridmap": True},
        },
    )
    profile_path = save_data_profile(run_dir, data_profile)
    plan_path = save_workflow_plan(run_dir, plan)

    assert planning_path == run_dir / "planning_notes.json"
    assert first_observation_path == run_dir / "observations.json"
    assert second_observation_path == run_dir / "observations.json"
    assert profile_path == run_dir / "data_profile.json"
    assert plan_path == run_dir / "plan.json"

    for path in (planning_path, first_observation_path, profile_path, plan_path):
        assert path.exists()
        json.loads(path.read_text(encoding="utf-8"))

    observations = json.loads(first_observation_path.read_text(encoding="utf-8"))
    assert [item["observation_id"] for item in observations] == ["obs_001", "obs_002"]

    loaded = load_workflow_artifacts(run_dir)
    assert loaded["planning_notes"] == planning_notes
    assert loaded["observations"] == observations
    assert loaded["data_profile"] == data_profile
    assert loaded["plan"] == plan


def test_workflow_run_dir_uses_context_root_and_server_date_not_sample_path(tmp_path):
    ctx = ToolContext(
        working_dir=str(tmp_path / "local_sample" / "raw_data" / "20270101"),
        artifacts_dir=str(tmp_path / "server_artifacts"),
    )
    created_at = datetime(2026, 6, 10, 12, 34, 56, tzinfo=timezone.utc)

    run_id = make_workflow_run_id(
        scenario="navigation_vla",
        date="20270605",
        created_at=created_at,
    )
    run_dir = build_workflow_run_dir(
        ctx,
        scenario="navigation_vla",
        date="20270605",
        created_at=created_at,
    )

    assert run_id == "vla_navigation_vla_20270605_20260610123456"
    assert run_dir == (
        tmp_path
        / "server_artifacts"
        / "vla_workflow_runs"
        / "20270605"
        / "vla_navigation_vla_20270605_20260610123456"
    )
    assert run_dir.exists()
    assert "20270101" not in str(run_dir)


def test_plan_agent_memory_notes_include_required_navigation_fields():
    notes = build_planning_notes(
        user_inputs={"date": "20270515", "scene_mode": "out"},
        scenario="navigation_vla",
    )

    assert notes["notes_id"] == "notes_20270515_navigation_vla_001"
    assert notes["scenario"] == "navigation_vla"
    assert notes["source_docs"] == ["navigation_vla.md"]
    assert notes["user_inputs"]["date"] == "20270515"
    assert notes["understood_rules"]
    assert "gridmap_artifacts" in notes["required_observations"]
    assert notes["unknowns"] == notes["required_observations"]
    assert notes["status"] == "need_inspection"


def test_plan_agent_generates_20270515_copy_existing_gridmap_plan():
    result = _run_plan(date="20270515", topic_schema="u_legacy_topics")
    profile = result["data_profile"]
    plan = result["plan"]

    assert profile.topics.topic_schema == "u_legacy_topics"
    assert profile.sync.query_raw_dir == "lidar_points"
    assert profile.gridmap.gridmap_source == "existing_gridmap_artifact"
    assert profile.stage_variants["gridmap_processing"].variant == "copy_existing_artifact"
    assert _stage_by_kind(plan, "gridmap_processing").tool == "vla_prepare_gridmap"
    assert _stage_by_kind(plan, "gridmap_processing").variant == "copy_existing_artifact"
    assert _stage_by_kind(plan, "projection_and_trajectory").variant == "cjl_with_gridmap"
    assert _stage_by_kind(plan, "validate_outputs").variant == "expect_gridmap"
    assert plan.approval_required is True


def test_plan_agent_generates_20270515_pointcloud_gridmap_plan_when_generator_available():
    result = _run_plan(
        date="20270515",
        topic_schema="u_legacy_topics",
        gridmap_source="unknown",
        pointcloud_status="available",
    )
    profile = result["data_profile"]
    plan = result["plan"]

    assert profile.gridmap.gridmap_source == "generated_from_pointcloud"
    assert profile.stage_variants["gridmap_processing"].variant == "pointcloud_to_gridmap"
    assert _stage_by_kind(plan, "gridmap_processing").variant == "pointcloud_to_gridmap"


def test_plan_agent_skips_20270515_gridmap_processing_when_projection_input_ready():
    result = _run_plan(
        date="20270515",
        topic_schema="u_legacy_topics",
        projection_ready=True,
    )
    plan = result["plan"]

    assert "gridmap_processing" not in {
        stage.stage_kind for stage in plan.active_stages
    }
    skipped = {stage.stage_kind: stage for stage in plan.skipped_stages}
    assert skipped["gridmap_processing"].reason == "grid_map_already_prepared"
    assert skipped["gridmap_processing"].evidence == ["obs_gridmap"]


def test_plan_agent_generates_20270605_copy_existing_gridmap_plan():
    result = _run_plan(date="20270605", topic_schema="go2w_current_topics")
    profile = result["data_profile"]
    plan = result["plan"]

    assert profile.topics.topic_schema == "go2w_current_topics"
    assert profile.sync.query_raw_dir == "rs32_lidar_points"
    assert profile.stage_variants["gridmap_processing"].variant == "copy_existing_artifact"
    assert _stage_by_kind(plan, "gridmap_processing").tool == "vla_prepare_gridmap"
    assert _stage_by_kind(plan, "gridmap_processing").variant == "copy_existing_artifact"
    assert _stage_by_kind(plan, "projection_and_trajectory").variant == "cjl_0525_with_gridmap"
    assert _stage_by_kind(plan, "validate_outputs").variant == "expect_gridmap"


def test_plan_agent_generates_20270605_pointcloud_gridmap_plan_when_generator_available():
    result = _run_plan(
        date="20270605",
        topic_schema="go2w_current_topics",
        gridmap_source="unknown",
        pointcloud_status="available",
    )
    profile = result["data_profile"]
    plan = result["plan"]

    assert profile.gridmap.gridmap_source == "generated_from_pointcloud"
    assert profile.stage_variants["gridmap_processing"].variant == "pointcloud_to_gridmap"
    assert _stage_by_kind(plan, "gridmap_processing").variant == "pointcloud_to_gridmap"
    assert _stage_by_kind(plan, "projection_and_trajectory").variant == "cjl_0525_with_gridmap"


def test_plan_agent_skips_20270605_gridmap_processing_when_projection_input_ready():
    result = _run_plan(
        date="20270605",
        topic_schema="go2w_current_topics",
        projection_ready=True,
    )
    plan = result["plan"]

    assert "gridmap_processing" not in {
        stage.stage_kind for stage in plan.active_stages
    }
    skipped = {stage.stage_kind: stage for stage in plan.skipped_stages}
    assert skipped["gridmap_processing"].reason == "grid_map_already_prepared"
    assert skipped["gridmap_processing"].evidence == ["obs_gridmap"]


def test_plan_agent_blocks_when_gridmap_source_and_generator_are_missing():
    result = _run_plan(
        date="20270605",
        topic_schema="go2w_current_topics",
        gridmap_source="unknown",
        pointcloud_status="placeholder",
    )
    profile = result["data_profile"]
    plan = result["plan"]

    assert profile.blocking_issues[0].type == "missing_gridmap_source_or_generator"
    assert plan.status == "failed"
    assert plan.active_stages == []
    assert plan.approval_required is False


def test_plan_agent_manipulation_request_returns_unsupported_plan():
    result = deterministic_plan_vla_workflow(
        user_inputs={"scenario": "manipulation_vla", "date": "20270605"},
        observations=[],
        catalog=_copy_catalog(),
    )
    plan = result["plan"]

    assert result["data_profile"] is None
    assert plan.scenario == "manipulation_vla"
    assert plan.status == "failed"
    assert plan.active_stages == []
    assert plan.skipped_stages[0].reason == "unsupported_scenario"


def test_plan_agent_blocks_custom_topics_when_mapping_variant_is_unavailable():
    result = _run_plan(
        date="20270605",
        topic_schema="custom_topics",
        gridmap_source="existing_gridmap_artifact",
    )
    profile = result["data_profile"]
    plan = result["plan"]

    issue_types = {issue.type for issue in profile.blocking_issues}
    assert "missing_custom_topic_mapping_support" in issue_types
    assert plan.active_stages == []

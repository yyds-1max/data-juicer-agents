from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationVLADataProfile,
)
from data_juicer_agents.capabilities.vla_workflow.profile.validate_navigation import (
    validate_navigation_data_profile_model,
)
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
from data_juicer_agents.tools.vla.inspect_datatoolbox_variants.logic import (
    inspect_datatoolbox_variants,
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
from data_juicer_agents.tools.vla.inspect_trajectory_script_variants.logic import (
    inspect_trajectory_script_variants,
)
from data_juicer_agents.tools.vla.registry import TOOL_SPECS


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "vla" / "navigation"


def _minimal_u_legacy_profile(**overrides):
    profile = {
        "dataset": {
            "date": "20270515",
            "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
            "raw_date_dir": "/media/heying/hy_data1/VLADatasets/raw_data/20270515",
            "raw_work_dir": "/media/heying/hy_data1/VLADatasets/raw_data/20270515_temp",
            "clip_root": "/media/heying/hy_data1/VLADatasets/clip_data",
            "finish_root": "/media/heying/hy_data1/VLADatasets/finish_data",
            "trajectory_root": (
                "/media/heying/hy_data1/Trajectory_visualization/"
                "Object_location_gh_v3_fisheye_five_U_add_SF_01"
            ),
            "scene_mode": "out",
            "selected_segments": ["20260515_102948"],
        },
        "raw_segments": [
            {
                "name": "20260515_102948",
                "path": (
                    "/media/heying/hy_data1/VLADatasets/raw_data/"
                    "20270515_temp/20260515_102948"
                ),
                "has_db3": True,
                "has_metadata_yaml": True,
                "db3_files": ["20260515_102948_0.db3"],
                "duration_ns": 21872824365,
                "message_count": 17655,
            }
        ],
        "topics": {
            "raw_topics": [
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
            ],
            "topic_schema": "u_legacy_topics",
            "topic_mapping_variant": "cam5_lidar_points_utlidar_odom",
            "required_roles_present": True,
            "missing_required_roles": [],
        },
        "sync": {
            "query_raw_dir": "lidar_points",
            "query_canonical_dir": "r32_rslidar_points",
        },
        "processing_state": {},
        "localization": {
            "source": "odom",
            "canonical_output": "Ins_compatible_odom",
            "requires_odom_convert": True,
        },
        "calibration": {
            "platform_hint": "u",
            "sensor_params_dir": (
                "/media/heying/hy_data1/Trajectory_visualization/"
                "Object_location_gh_v3_fisheye_five_U_add_SF_01/"
                "NoobScenes/params/20260409_U/sensors"
            ),
            "sensor_params_status": "present",
        },
        "gridmap": {
            "raw_gridmap_topic_present": False,
            "gridmap_source": "existing_gridmap_artifact",
            "requires_gridmap_processing": True,
            "expect_gridmap_output": True,
        },
        "stage_variants": {
            "extract_and_sync": {
                "variant": "u_legacy_topics",
                "reason": "raw topics match the legacy U navigation schema",
                "evidence": ["obs_raw_metadata_topics"],
            },
            "build_noobscenes_inputs": {
                "variant": "odom_convert_resize",
                "reason": "raw localization is odom",
                "evidence": ["obs_raw_metadata_topics"],
            },
            "gridmap_processing": {
                "variant": "copy_existing_artifact",
                "reason": "grid_map exists as an artifact",
                "evidence": ["obs_gridmap_artifacts"],
            },
            "validate_outputs": {
                "variant": "expect_gridmap",
                "reason": "navigation final output requires grid_map",
                "evidence": ["obs_gridmap_policy"],
            },
        },
    }
    profile.update(overrides)
    return profile


def test_navigation_vla_data_profile_accepts_minimal_u_legacy_profile():
    profile = NavigationVLADataProfile.model_validate(_minimal_u_legacy_profile())
    result = validate_navigation_data_profile_model(profile)

    assert profile.scenario == "navigation_vla"
    assert profile.topics.topic_schema == "u_legacy_topics"
    assert profile.blocking_issues == []
    assert result["ok"] is True
    assert result["errors"] == []


def test_navigation_profile_validation_reports_missing_localization_source():
    profile = NavigationVLADataProfile.model_validate(
        _minimal_u_legacy_profile(
            localization={
                "source": "unknown",
                "canonical_output": "",
                "requires_odom_convert": False,
            }
        )
    )

    result = validate_navigation_data_profile_model(profile)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "missing_localization_source"


def _topics_from_fixture(date: str):
    payload = yaml.safe_load((FIXTURE_ROOT / date / "metadata.yaml").read_text(encoding="utf-8"))
    topics = []
    for item in payload["rosbag2_bagfile_information"]["topics_with_message_count"]:
        metadata = item["topic_metadata"]
        topics.append(
            {
                "name": metadata["name"],
                "type": metadata["type"],
                "message_count": item["message_count"],
            }
        )
    return topics


def test_plan_agent_inspection_tools_read_navigation_dataset_facts(tmp_path):
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    finish_root = tmp_path / "finish_data"
    trajectory_root = tmp_path / "Trajectory_visualization" / "Object_location"
    segment = raw_root / "20270605" / "20260605_152856"
    segment.mkdir(parents=True)
    shutil.copy2(FIXTURE_ROOT / "20270605" / "metadata.yaml", segment / "metadata.yaml")
    (segment / "20260605_152856_0.db3").write_text("", encoding="utf-8")

    raw_layout = inspect_raw_layout(date="20270605", raw_root=str(raw_root))
    metadata = inspect_rosbag_metadata(segment_path=str(segment))
    topic_schema = classify_navigation_topic_schema(topics=metadata["topics"], date="20990101")
    sync = infer_sync_policy(topic_schema=topic_schema["topic_schema"], topics=metadata["topics"])
    localization = infer_localization_policy(topics=metadata["topics"], scene_mode="out")

    assert raw_layout["ok"] is True
    assert raw_layout["raw_date_dir"] == str(raw_root / "20270605")
    assert raw_layout["raw_temp_dir"] == str(raw_root / "20270605_temp")
    assert raw_layout["segments"][0]["db3_files"] == ["20260605_152856_0.db3"]
    assert raw_layout["segments"][0]["has_db3_shm"] is False
    assert metadata["ok"] is True
    assert metadata["relative_file_paths"] == ["20260605_152856_0.db3"]
    assert topic_schema["topic_schema"] == "go2w_current_topics"
    assert topic_schema["topic_mapping_variant"] == "cam4_rs32_sport_odom"
    assert sync["query_raw_dir"] == "rs32_lidar_points"
    assert sync["query_canonical_dir"] == "r32_rslidar_points"
    assert localization["source"] == "odom"
    assert localization["stage_variant"]["variant"] == "odom_convert_resize"


def test_inspect_rosbag_metadata_reports_parse_failure(tmp_path):
    segment = tmp_path / "raw_data" / "20270605" / "bad_segment"
    segment.mkdir(parents=True)
    (segment / "metadata.yaml").write_text("not: [valid", encoding="utf-8")

    result = inspect_rosbag_metadata(segment_path=str(segment))

    assert result["ok"] is False
    assert result["error_type"] == "metadata_parse_failed"


def test_plan_agent_inspection_tools_read_script_and_artifact_facts(tmp_path):
    data_toolbox_src = tmp_path / "DataToolbox" / "src"
    data_toolbox_src.mkdir(parents=True)
    (data_toolbox_src / "1_extract_data_from_bag_multi_process_ros2_U_legacy.py").write_text(
        "/cam_video5/csi_cam/image_raw/compressed\n/lidar_points\n/utlidar/robot_odom_systime\n",
        encoding="utf-8",
    )
    (data_toolbox_src / "2_sync_data_multi_process_U_legacy.py").write_text(
        "lidar_points r32_rslidar_points\n",
        encoding="utf-8",
    )
    (data_toolbox_src / "1_extract_data_from_bag_multi_process_ros2_U.py").write_text(
        "/cam_video4/csi_cam/image_raw/compressed\n/rs32_lidar_points\n/sport_odom\n",
        encoding="utf-8",
    )
    (data_toolbox_src / "2_sync_data_multi_process_U.py").write_text(
        "rs32_lidar_points r32_rslidar_points\n",
        encoding="utf-8",
    )

    trajectory_root = tmp_path / "Trajectory_visualization" / "Object_location"
    sensors = trajectory_root / "NoobScenes" / "params" / "20260529_go2w" / "sensors"
    sensors.mkdir(parents=True)
    (sensors / "fisheye_front.json").write_text("{}", encoding="utf-8")
    (sensors / "r32_rslidar_points.json").write_text("{}", encoding="utf-8")
    (trajectory_root / "2_pt_project").mkdir(parents=True)
    (trajectory_root / "2_pt_project" / "2_othermethod_cjl.py").write_text(
        "print('project')\n", encoding="utf-8"
    )
    (trajectory_root / "2_pt_project" / "2_othermethod_cjl_0525.py").write_text(
        "print('project 0525')\n", encoding="utf-8"
    )
    (trajectory_root / "2_pt_project" / "3_move_dir.py").write_text(
        "print('move grid_map')\n", encoding="utf-8"
    )
    (trajectory_root / "other_code").mkdir(parents=True)
    (trajectory_root / "other_code" / "cp_gridmap.py").write_text("print('cp')\n", encoding="utf-8")

    clip_gridmap = (
        tmp_path
        / "clip_data"
        / "20270605"
        / "20260605_152856"
        / "sync_data"
        / "20260605_152856_zhigu_wuhan_0"
        / "grid_map"
    )
    clip_gridmap.mkdir(parents=True)
    final_date = tmp_path / "finish_data" / "20270605" / "final"
    for name in ("trajectory", "speed", "world", "rout_plot", "grid_map"):
        (final_date / name).mkdir(parents=True)
    sample_clip = (
        tmp_path
        / "finish_data"
        / "20270605_temp"
        / "samples"
        / "20270605"
        / "20260605_152856_zhigu_wuhan_0"
    )
    (sample_clip / "project_npy").mkdir(parents=True)
    (sample_clip / "master_black_black.yaml").write_text("box: []\n", encoding="utf-8")

    variants = inspect_datatoolbox_variants(data_toolbox_src=str(data_toolbox_src))
    calibration = inspect_calibration_assets(
        trajectory_root=str(trajectory_root),
        topic_schema="go2w_current_topics",
    )
    processing_state = inspect_processing_state(
        date="20270605",
        selected_segments=["20260605_152856"],
        clip_root=str(tmp_path / "clip_data"),
        finish_root=str(tmp_path / "finish_data"),
    )
    gridmap = inspect_gridmap_artifacts(
        date="20270605",
        selected_segments=["20260605_152856"],
        topics=_topics_from_fixture("20270605"),
        clip_root=str(tmp_path / "clip_data"),
        finish_root=str(tmp_path / "finish_data"),
    )
    trajectory = inspect_trajectory_script_variants(trajectory_root=str(trajectory_root))

    assert variants["variants"]["u_legacy_topics"]["status"] == "available"
    assert variants["variants"]["go2w_current_topics"]["status"] == "available"
    assert calibration["recommended_sensor_params_dir"] == str(sensors)
    assert calibration["sensor_params_status"] == "present"
    assert processing_state["state"] == "partial"
    assert processing_state["has_sync_data"] is True
    assert processing_state["has_final_grid_map"] is True
    assert gridmap["raw_gridmap_topic_present"] is False
    assert gridmap["gridmap_source"] == "existing_gridmap_artifact"
    assert gridmap["artifact_locations"] == ["clip_sync", "finish_final"]
    assert trajectory["variants"]["cjl_with_gridmap"]["available"] is True
    assert trajectory["variants"]["cjl_0525_with_gridmap"]["available"] is True
    assert trajectory["projection_implicitly_calls_cp_gridmap"] is False


def test_unknown_topics_create_blocking_sync_and_localization_issues():
    topics = [{"name": "/camera/only", "type": "sensor_msgs/msg/CompressedImage"}]

    classified = classify_navigation_topic_schema(topics=topics, date="20270605")
    sync = infer_sync_policy(topic_schema=classified["topic_schema"], topics=topics)
    localization = infer_localization_policy(topics=topics, scene_mode="out")

    assert classified["topic_schema"] == "unknown_topics"
    assert sync["ok"] is False
    assert sync["blocking_issues"][0]["type"] == "unknown_topic_schema"
    assert localization["ok"] is False
    assert localization["blocking_issues"][0]["type"] == "missing_localization_topic"


def test_plan_agent_inspection_tools_are_registered_read_only():
    expected = {
        "vla_inspect_raw_layout",
        "vla_inspect_rosbag_metadata",
        "vla_classify_navigation_topic_schema",
        "vla_infer_sync_policy",
        "vla_inspect_datatoolbox_variants",
        "vla_inspect_processing_state",
        "vla_inspect_calibration_assets",
        "vla_infer_localization_policy",
        "vla_inspect_gridmap_artifacts",
        "vla_inspect_trajectory_script_variants",
    }

    specs = {spec.name: spec for spec in TOOL_SPECS}

    assert expected.issubset(specs)
    for name in expected:
        assert specs[name].effects == "read"
        assert specs[name].confirmation == "none"
        assert {"vla", "read"}.issubset(set(specs[name].tags))

    result = specs["vla_classify_navigation_topic_schema"].execute(
        ToolContext(),
        {"topics": _topics_from_fixture("20270605"), "date": "20990101"},
    )
    assert result.ok is True
    assert result.data["topic_schema"] == "go2w_current_topics"

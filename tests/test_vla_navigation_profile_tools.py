from __future__ import annotations

from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationVLADataProfile,
)
from data_juicer_agents.capabilities.vla_workflow.profile.validate_navigation import (
    validate_navigation_data_profile_model,
)


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

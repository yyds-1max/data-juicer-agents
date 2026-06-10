from __future__ import annotations

from typing import Any

from data_juicer_agents.tools.vla._shared.inspection import (
    has_role,
    has_topic,
    normalize_topics,
    required_roles,
    topic_last_segment,
)


def classify_navigation_topic_schema(
    *,
    topics: list[dict[str, Any]],
    date: str | None = None,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_topics(topics)
    roles_present, missing_roles = required_roles(normalized)
    schema = "unknown_topics"
    variant = ""
    if (
        has_topic(normalized, "/cam_video5/csi_cam/image_raw/compressed")
        and has_topic(normalized, "/lidar_points")
        and has_topic(normalized, "/utlidar/robot_odom_systime")
    ):
        schema = "u_legacy_topics"
        variant = "cam5_lidar_points_utlidar_odom"
    elif (
        has_topic(normalized, "/cam_video4/csi_cam/image_raw/compressed")
        and has_topic(normalized, "/rs32_lidar_points")
        and has_topic(normalized, "/sport_odom")
    ):
        schema = "go2w_current_topics"
        variant = "cam4_rs32_sport_odom"
    elif (
        has_role(normalized, "front_fisheye_image")
        and has_role(normalized, "lidar")
        and has_topic(normalized, "/drivers/ins/Ins")
    ):
        schema = "shanmao_ins_topics"
        variant = "front_fisheye_lidar_ins"
    elif roles_present:
        schema = "custom_topics"
        variant = "custom_role_mapping"

    lidar_dirs = [
        topic_last_segment(item["name"]) for item in normalized if item.get("role") == "lidar"
    ]
    return {
        "ok": schema != "unknown_topics",
        "date": date,
        "topics": normalized,
        "topic_schema": schema,
        "topic_mapping_variant": variant,
        "required_roles_present": roles_present,
        "missing_required_roles": missing_roles,
        "sync_query_candidates": lidar_dirs,
        "run_id": run_id,
        "log_dir": log_dir,
    }

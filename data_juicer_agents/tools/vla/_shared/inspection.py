from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def topic_last_segment(topic_name: str) -> str:
    return str(topic_name or "").rstrip("/").rsplit("/", maxsplit=1)[-1]


def normalize_topic(raw: dict[str, Any]) -> dict[str, Any]:
    name = str(raw.get("name", ""))
    topic_type = str(raw.get("type", ""))
    role = str(raw.get("role") or _infer_role(name, topic_type))
    canonical_dir = str(raw.get("canonical_dir") or _canonical_dir(name, role))
    result = {
        "name": name,
        "type": topic_type,
        "role": role,
        "canonical_dir": canonical_dir,
    }
    if raw.get("message_count") is not None:
        result["message_count"] = raw.get("message_count")
    return result


def normalize_topics(topics: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return [normalize_topic(item) for item in topics or []]


def has_topic(topics: list[dict[str, Any]], name: str) -> bool:
    return any(item.get("name") == name for item in topics)


def has_role(topics: list[dict[str, Any]], role: str) -> bool:
    return any(item.get("role") == role for item in topics)


def required_roles(topics: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    present = {str(item.get("role", "")) for item in topics}
    missing = []
    if "front_fisheye_image" not in present:
        missing.append("front_fisheye_image")
    if "lidar" not in present:
        missing.append("lidar")
    if not ({"localization_odom", "localization_ins"} & present):
        missing.append("localization")
    return not missing, missing


def read_rosbag_metadata(metadata_path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
    bag_info = payload.get("rosbag2_bagfile_information") or {}
    topics = []
    for item in bag_info.get("topics_with_message_count") or []:
        metadata = item.get("topic_metadata") or {}
        topics.append(
            normalize_topic(
                {
                    "name": metadata.get("name", ""),
                    "type": metadata.get("type", ""),
                    "message_count": item.get("message_count"),
                }
            )
        )
    return {
        "version": bag_info.get("version"),
        "duration_ns": _duration_ns(bag_info.get("duration")),
        "message_count": bag_info.get("message_count"),
        "relative_file_paths": list(bag_info.get("relative_file_paths") or []),
        "topics": topics,
    }


def script_contains_all(path: Path, needles: list[str]) -> bool:
    if not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return all(needle in text for needle in needles)


def existing_dirs(paths: list[Path]) -> list[str]:
    return [str(path) for path in paths if path.is_dir()]


def gridmap_topic_present(topics: list[dict[str, Any]] | None) -> bool:
    normalized = normalize_topics(topics)
    return any(item.get("role") == "gridmap" for item in normalized)


def _duration_ns(raw: Any) -> int | None:
    if isinstance(raw, dict):
        value = raw.get("nanoseconds")
    else:
        value = raw
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _infer_role(name: str, topic_type: str) -> str:
    lowered_name = name.lower()
    lowered_type = topic_type.lower()
    if "grid" in lowered_name and "map" in lowered_name:
        return "gridmap"
    if "odometry" in lowered_type or "odom" in lowered_name:
        return "localization_odom"
    if name == "/drivers/ins/Ins" or lowered_name.endswith("/ins") or "ins" in lowered_type:
        return "localization_ins"
    if "pointcloud2" in lowered_type or "lidar" in lowered_name or "points" in lowered_name:
        return "lidar"
    if "image" in lowered_type or "image" in lowered_name or "cam" in lowered_name:
        return "front_fisheye_image"
    return ""


def _canonical_dir(name: str, role: str) -> str:
    if role == "front_fisheye_image":
        return "fisheye_front"
    if role == "lidar":
        return "r32_rslidar_points"
    if role == "localization_odom":
        return "odom"
    if role == "localization_ins":
        return "Ins"
    if role == "gridmap":
        return "grid_map"
    return topic_last_segment(name)

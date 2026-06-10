from __future__ import annotations

from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.inspection import script_contains_all


_VARIANTS = {
    "u_legacy_topics": {
        "extract": "1_extract_data_from_bag_multi_process_ros2_U_legacy.py",
        "sync": "2_sync_data_multi_process_U_legacy.py",
        "extract_needles": [
            "/cam_video5/csi_cam/image_raw/compressed",
            "/lidar_points",
            "/utlidar/robot_odom_systime",
        ],
        "sync_needles": ["lidar_points", "r32_rslidar_points"],
    },
    "go2w_current_topics": {
        "extract": "1_extract_data_from_bag_multi_process_ros2_U.py",
        "sync": "2_sync_data_multi_process_U.py",
        "extract_needles": [
            "/cam_video4/csi_cam/image_raw/compressed",
            "/rs32_lidar_points",
            "/sport_odom",
        ],
        "sync_needles": ["rs32_lidar_points", "r32_rslidar_points"],
    },
}


def inspect_datatoolbox_variants(
    *,
    data_toolbox_src: str,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    root = Path(data_toolbox_src).expanduser()
    variants = {}
    for variant, config in _VARIANTS.items():
        extract_path = root / config["extract"]
        sync_path = root / config["sync"]
        extract_ok = script_contains_all(extract_path, config["extract_needles"])
        sync_ok = script_contains_all(sync_path, config["sync_needles"])
        variants[variant] = {
            "extract_script": str(extract_path),
            "sync_script": str(sync_path),
            "script_exists": extract_path.is_file() and sync_path.is_file(),
            "extract_supports_schema": extract_ok,
            "sync_supports_schema": sync_ok,
            "status": "available" if extract_ok and sync_ok else "placeholder",
        }
    return {
        "ok": True,
        "data_toolbox_src": str(root),
        "variants": variants,
        "run_id": run_id,
        "log_dir": log_dir,
    }

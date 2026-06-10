from __future__ import annotations

from pathlib import Path
from typing import Any


_RECOMMENDED_DIR = {
    "u_legacy_topics": "20260409_U",
    "go2w_current_topics": "20260529_go2w",
}
_REQUIRED_SENSOR_FILES = ("fisheye_front.json", "r32_rslidar_points.json")


def inspect_calibration_assets(
    *,
    trajectory_root: str,
    topic_schema: str,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    root = Path(trajectory_root).expanduser()
    params_root = root / "NoobScenes" / "params"
    candidates = []
    for sensors in sorted(params_root.glob("*/sensors"), key=lambda item: str(item)):
        missing = [name for name in _REQUIRED_SENSOR_FILES if not (sensors / name).is_file()]
        candidates.append(
            {
                "name": sensors.parent.name,
                "sensor_params_dir": str(sensors),
                "status": "present" if not missing else "incomplete",
                "missing_files": missing,
            }
        )

    recommended_name = _RECOMMENDED_DIR.get(topic_schema, "")
    recommended = next(
        (item for item in candidates if item["name"] == recommended_name),
        None,
    )
    recommended_dir = (
        params_root / recommended_name / "sensors" if recommended_name else Path("")
    )
    missing = [
        name for name in _REQUIRED_SENSOR_FILES if recommended_name and not (recommended_dir / name).is_file()
    ]
    status = "unknown"
    if recommended_name:
        status = "present" if recommended and recommended["status"] == "present" else "missing"
        if missing and recommended_dir.is_dir():
            status = "incomplete"
    return {
        "ok": status == "present",
        "trajectory_root": str(root),
        "topic_schema": topic_schema,
        "candidates": candidates,
        "recommended_sensor_params_dir": str(recommended_dir) if recommended_name else "",
        "sensor_params_status": status,
        "missing_files": missing,
        "stage_variant": {
            "stage": "prepare_finish_dataset",
            "variant": f"{recommended_name}_sensor_params" if recommended_name else "unknown",
        },
        "run_id": run_id,
        "log_dir": log_dir,
    }

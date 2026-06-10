from __future__ import annotations

from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.inspection import existing_dirs, gridmap_topic_present
from data_juicer_agents.tools.vla._shared.selection import normalize_selected_segments, validate_date


def inspect_gridmap_artifacts(
    *,
    date: str,
    clip_root: str,
    finish_root: str,
    topics: list[dict[str, Any]] | None = None,
    selected_segments: list[str] | None = None,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    selected = normalize_selected_segments(selected_segments or [])
    clip_date = Path(clip_root).expanduser() / date
    finish = Path(finish_root).expanduser()
    finish_temp_samples = finish / f"{date}_temp" / "samples" / date
    finish_date = finish / date
    raw_present = gridmap_topic_present(topics)

    clip_paths = []
    segments = selected or _child_names(clip_date)
    for segment in segments:
        clip_paths.extend((clip_date / segment / "sync_data").glob("*/grid_map"))
    finish_temp_paths = list(finish_temp_samples.glob("*/grid_map"))
    finish_final_paths = list(finish_date.rglob("grid_map"))

    artifact_locations = []
    artifacts = []
    if existing_dirs(clip_paths):
        artifact_locations.append("clip_sync")
        artifacts.extend(existing_dirs(clip_paths))
    if existing_dirs(finish_temp_paths):
        artifact_locations.append("finish_temp_samples")
        artifacts.extend(existing_dirs(finish_temp_paths))
    if existing_dirs(finish_final_paths):
        artifact_locations.append("finish_final")
        artifacts.extend(existing_dirs(finish_final_paths))

    source = "unknown"
    if raw_present:
        source = "raw_topic"
    elif artifacts:
        source = "existing_gridmap_artifact"
    return {
        "ok": True,
        "date": date,
        "raw_gridmap_topic_present": raw_present,
        "available_gridmap_artifacts": artifacts,
        "artifact_locations": artifact_locations,
        "projection_input_gridmap_ready": bool(existing_dirs(finish_temp_paths)),
        "gridmap_source": source,
        "run_id": run_id,
        "log_dir": log_dir,
    }


def _child_names(path: Path) -> list[str]:
    if not path.is_dir():
        return []
    return [child.name for child in sorted(path.iterdir(), key=lambda item: item.name) if child.is_dir()]

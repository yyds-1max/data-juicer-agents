from __future__ import annotations

from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.selection import normalize_selected_segments, validate_date


def inspect_processing_state(
    *,
    date: str,
    clip_root: str,
    finish_root: str,
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

    sync_segments = []
    discovered_segments = []
    if clip_date.is_dir():
        discovered_segments = [
            path.name for path in clip_date.iterdir() if path.is_dir()
        ]
    for segment in selected or discovered_segments:
        if (clip_date / segment / "sync_data").is_dir():
            sync_segments.append(segment)

    checks = {
        "has_sync_data": bool(sync_segments),
        "has_finish_temp_samples": finish_temp_samples.is_dir(),
        "has_annotation_yaml": any(finish_temp_samples.glob("*/*.yaml")),
        "has_tracking_outputs": any(finish_temp_samples.glob("*/tracking"))
        or any(finish_temp_samples.glob("*/*tracking*")),
        "has_project_npy": any(finish_temp_samples.glob("*/project_npy")),
        "has_final_outputs": any((finish_date).rglob("trajectory"))
        or any((finish_date).rglob("speed"))
        or any((finish_date).rglob("world"))
        or any((finish_date).rglob("rout_plot")),
        "has_final_grid_map": any((finish_date).rglob("grid_map")),
    }
    present = sum(1 for value in checks.values() if value)
    state = "none"
    if present == len(checks):
        state = "complete"
    elif present:
        state = "partial"
    return {
        "ok": True,
        "date": date,
        "state": state,
        "sync_data_segments": sync_segments,
        "finish_temp_samples_dir": str(finish_temp_samples),
        **checks,
        "run_id": run_id,
        "log_dir": log_dir,
    }

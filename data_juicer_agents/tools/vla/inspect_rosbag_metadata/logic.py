from __future__ import annotations

from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.inspection import read_rosbag_metadata


def inspect_rosbag_metadata(
    *,
    segment_path: str | None = None,
    metadata_path: str | None = None,
    raw_root: str | None = None,
    date: str | None = None,
    segment: str | None = None,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    path = _resolve_metadata_path(
        segment_path=segment_path,
        metadata_path=metadata_path,
        raw_root=raw_root,
        date=date,
        segment=segment,
    )
    base = {
        "ok": False,
        "metadata_path": str(path) if path else "",
        "run_id": run_id,
        "log_dir": log_dir,
    }
    if path is None or not path.is_file():
        return {**base, "error_type": "metadata_missing", "topics": []}
    try:
        parsed = read_rosbag_metadata(path)
    except Exception as exc:
        return {
            **base,
            "error_type": "metadata_parse_failed",
            "error_message": str(exc),
            "topics": [],
        }
    return {**base, **parsed, "ok": True}


def _resolve_metadata_path(
    *,
    segment_path: str | None,
    metadata_path: str | None,
    raw_root: str | None,
    date: str | None,
    segment: str | None,
) -> Path | None:
    if metadata_path:
        return Path(metadata_path).expanduser()
    if segment_path:
        return Path(segment_path).expanduser() / "metadata.yaml"
    if raw_root and date and segment:
        return Path(raw_root).expanduser() / date / segment / "metadata.yaml"
    return None

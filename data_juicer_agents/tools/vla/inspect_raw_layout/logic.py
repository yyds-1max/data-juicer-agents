from __future__ import annotations

from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.selection import (
    normalize_selected_segments,
    sorted_child_dirs,
    validate_date,
)


def inspect_raw_layout(
    *,
    date: str,
    raw_root: str,
    selected_segments: list[str] | None = None,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    root = Path(raw_root).expanduser()
    raw_date_dir = root / date
    raw_temp_dir = root / f"{date}_temp"
    selected = set(normalize_selected_segments(selected_segments or []))
    children = sorted_child_dirs(raw_date_dir)
    if selected:
        children = [child for child in children if child.name in selected]

    segments = []
    for child in children:
        db3_files = sorted(item.name for item in child.glob("*.db3") if item.is_file())
        segments.append(
            {
                "name": child.name,
                "path": str(child),
                "has_db3": bool(db3_files),
                "has_metadata_yaml": (child / "metadata.yaml").is_file(),
                "db3_files": db3_files,
                "has_db3_shm": any(child.glob("*.db3-shm")),
                "has_db3_wal": any(child.glob("*.db3-wal")),
            }
        )

    return {
        "ok": raw_date_dir.is_dir(),
        "date": date,
        "raw_root": str(root),
        "raw_date_dir": str(raw_date_dir),
        "raw_temp_dir": str(raw_temp_dir),
        "segments": segments,
        "count": len(segments),
        "processing_state": {"has_raw_temp": raw_temp_dir.is_dir()},
        "run_id": run_id,
        "log_dir": log_dir,
        **({} if raw_date_dir.is_dir() else {"error_type": "missing_raw_date"}),
    }

from __future__ import annotations

from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.selection import (
    sorted_child_dirs,
    validate_date,
)

_STAGE = "list_clip_segments"


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def list_clip_segments(
    *,
    date: str,
    clip_root: str,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    clip_root_path = Path(clip_root).expanduser()
    clip_date_dir = clip_root_path / date
    logger = _logger(log_dir)
    base = {
        "date": date,
        "clip_root": str(clip_root_path),
        "clip_date_dir": str(clip_date_dir),
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting VLA clip segment listing",
            data=base,
        )

    if not clip_date_dir.is_dir():
        result = {
            "ok": False,
            "error_type": "missing_clip_date",
            **base,
            "segments": [],
            "count": 0,
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message="clip date directory is missing",
                data=result,
            )
        return result

    segments = []
    for segment_dir in sorted_child_dirs(clip_date_dir):
        sync_data_dir = segment_dir / "sync_data"
        segments.append(
            {
                "name": segment_dir.name,
                "path": str(segment_dir),
                "sync_data_dir": str(sync_data_dir),
                "has_sync_data": sync_data_dir.is_dir(),
            }
        )

    result = {"ok": True, **base, "segments": segments, "count": len(segments)}
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_end",
            ok=True,
            message="listed VLA clip segments",
            data=result,
        )
    return result

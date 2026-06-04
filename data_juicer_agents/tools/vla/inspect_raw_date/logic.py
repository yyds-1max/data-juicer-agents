from __future__ import annotations

from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.selection import sorted_child_dirs, validate_date

_STAGE = "inspect_raw_date"


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def inspect_raw_date(
    *,
    date: str,
    raw_root: str,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    date_dir = Path(raw_root).expanduser() / date
    logger = _logger(log_dir)
    base = {
        "date": date,
        "raw_root": str(Path(raw_root).expanduser()),
        "raw_date_dir": str(date_dir),
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting raw VLA date inspection",
            data=base,
        )

    if not date_dir.exists():
        result = {
            "ok": False,
            "error_type": "missing_raw_date",
            "segments": [],
            "count": 0,
            **base,
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message="raw date directory is missing",
                data=result,
            )
        return result

    segments = []
    warnings: list[str] = []
    for child in sorted_child_dirs(date_dir):
        has_metadata = (child / "metadata.yaml").exists()
        has_db3 = any(item.suffix == ".db3" for item in child.iterdir() if item.is_file())
        segment = {
            "name": child.name,
            "path": str(child),
            "has_metadata": has_metadata,
            "has_db3": has_db3,
        }
        if not has_metadata:
            warnings.append(f"{child.name} is missing metadata.yaml")
        if not has_db3:
            warnings.append(f"{child.name} has no .db3 files")
        segments.append(segment)

    result = {
        "ok": True,
        "segments": segments,
        "count": len(segments),
        "warnings": warnings,
        **base,
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_end",
            ok=True,
            message=f"found {len(segments)} raw VLA segments",
            data=result,
        )
    return result

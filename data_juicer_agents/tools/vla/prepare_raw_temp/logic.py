from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.selection import (
    normalize_selected_segments,
    validate_date,
)

_STAGE = "prepare_raw_temp"


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _link_status(target: Path) -> str:
    if target.is_symlink():
        return "existing_symlink"
    if target.exists():
        return "existing_path"
    return "planned"


def _skip(segment: str, reason: str, source: Path, target: Path) -> dict[str, str]:
    return {
        "segment": segment,
        "reason": reason,
        "source": str(source),
        "target": str(target),
    }


def _run_chown(owner: str, path: Path) -> dict[str, Any]:
    command = ["chown", "-R", owner, str(path)]
    proc = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return {
        "command": command,
        "path": str(path),
        "return_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def prepare_raw_temp(
    *,
    date: str,
    selected_segments: list[str],
    raw_root: str,
    clip_root: str,
    owner: str | None = None,
    dry_run: bool,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    segments = normalize_selected_segments(selected_segments)
    owner_value = str(owner).strip() if owner else None
    raw_root_path = Path(raw_root).expanduser()
    clip_root_path = Path(clip_root).expanduser()
    source_date = raw_root_path / date
    temp_dir = raw_root_path / f"{date}_temp"
    clip_date = clip_root_path / date
    logger = _logger(log_dir)

    links = []
    missing = []
    skipped_segments = []
    for segment in segments:
        source = source_date / segment
        target = temp_dir / segment
        status = _link_status(target)
        links.append(
            {
                "segment": segment,
                "source": str(source),
                "target": str(target),
                "status": status,
            }
        )
        if not source.is_dir():
            missing.append(segment)
            skipped_segments.append(_skip(segment, "missing_source", source, target))
        elif target.exists() and not target.is_symlink():
            skipped_segments.append(
                _skip(segment, "target_exists_not_symlink", source, target)
            )

    base = {
        "date": date,
        "dry_run": bool(dry_run),
        "owner": owner_value,
        "raw_root": str(raw_root_path),
        "clip_root": str(clip_root_path),
        "raw_date_dir": str(source_date),
        "raw_temp_dir": str(temp_dir),
        "clip_date_dir": str(clip_date),
        "selected_segments": segments,
        "links": links,
        "skipped_segments": skipped_segments,
        "chown_results": [],
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting raw VLA temp preparation",
            data=base,
        )

    if not segments:
        result = {"ok": False, "error_type": "no_selected_segments", **base}
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message="no raw VLA segments were selected",
                data=result,
            )
        return result

    if missing:
        result = {
            "ok": False,
            "error_type": "missing_segments",
            "missing_segments": missing,
            **base,
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message="one or more selected raw VLA segments are missing",
                data=result,
            )
        return result

    if not dry_run:
        temp_dir.mkdir(parents=True, exist_ok=True)
        clip_date.mkdir(parents=True, exist_ok=True)
        for link in links:
            target = Path(link["target"])
            if target.exists() or target.is_symlink():
                if target.exists() and not target.is_symlink():
                    link["status"] = "skipped"
                continue
            target.symlink_to(Path(link["source"]), target_is_directory=True)
            link["status"] = "created"
        if owner_value:
            base["chown_results"] = [
                _run_chown(owner_value, temp_dir),
                _run_chown(owner_value, clip_date),
            ]
            failed_chown = [
                item for item in base["chown_results"] if item["return_code"] != 0
            ]
            if failed_chown:
                result = {
                    "ok": False,
                    "error_type": "chown_failed",
                    "failed_chown": failed_chown,
                    **base,
                }
                if logger:
                    logger.event(
                        stage=_STAGE,
                        event_type="stage_end",
                        ok=False,
                        message="raw VLA temp preparation chown failed",
                        data=result,
                    )
                return result

    result = {"ok": True, **base}
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_end",
            ok=True,
            message="prepared raw VLA temp links" if not dry_run else "planned raw VLA temp links",
            data=result,
        )
    return result

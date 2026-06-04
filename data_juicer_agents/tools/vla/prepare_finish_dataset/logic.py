from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.selection import (
    normalize_selected_segments,
    sorted_child_dirs,
    validate_date,
)

_STAGE = "prepare_finish_dataset"
_COPIED_SUBDIRS = ("fisheye_front", "r32_rslidar_points")
_CLIP_PREFIXES = ("2025", "2026")


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _default_sensor_params_dir(trajectory_root: Path) -> Path:
    return trajectory_root / "NoobScenes" / "params" / "20260409_U" / "sensors"


def _find_clip_sources(
    *,
    date: str,
    selected_segments: list[str],
    clip_root: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    clips_by_name: dict[str, dict[str, str]] = {}
    missing_sync_data = []
    for segment in selected_segments:
        sync_data = clip_root / date / segment / "sync_data"
        if not sync_data.is_dir():
            missing_sync_data.append(
                {"segment": segment, "sync_data_dir": str(sync_data)}
            )
            continue
        for clip_dir in sorted_child_dirs(sync_data):
            if not clip_dir.name.startswith(_CLIP_PREFIXES):
                continue
            clips_by_name.setdefault(
                clip_dir.name,
                {
                    "clip_name": clip_dir.name,
                    "segment": segment,
                    "source": str(clip_dir),
                },
            )
    return list(clips_by_name.values()), missing_sync_data


def _copy_dir(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def prepare_finish_dataset(
    *,
    date: str,
    selected_segments: list[str],
    scene_mode: str,
    clip_root: str,
    finish_root: str,
    trajectory_root: str,
    sensor_params_dir: str | None,
    dry_run: bool,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    selected = normalize_selected_segments(selected_segments)
    if scene_mode not in {"in", "out"}:
        raise ValueError("scene_mode must be 'in' or 'out'")

    clip_root_path = Path(clip_root).expanduser()
    finish_root_path = Path(finish_root).expanduser()
    trajectory_root_path = Path(trajectory_root).expanduser()
    sensors_src = (
        Path(sensor_params_dir).expanduser()
        if sensor_params_dir
        else _default_sensor_params_dir(trajectory_root_path)
    )
    save_path = finish_root_path / date
    save_path_temp = finish_root_path / f"{date}_temp"
    save_path_date = save_path_temp / "samples" / date
    logger = _logger(log_dir)
    base = {
        "date": date,
        "scene_mode": scene_mode,
        "selected_segments": selected,
        "clip_root": str(clip_root_path),
        "finish_root": str(finish_root_path),
        "trajectory_root": str(trajectory_root_path),
        "sensor_params_dir": str(sensors_src),
        "save_path": str(save_path),
        "save_path_temp": str(save_path_temp),
        "save_path_date": str(save_path_date),
        "dry_run": bool(dry_run),
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting VLA finish dataset preparation",
            data=base,
        )

    if not selected:
        result = {
            "ok": False,
            "error_type": "no_selected_segments",
            **base,
            "clips": [],
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message="no VLA clip segments were selected",
                data=result,
            )
        return result

    discovered, missing_sync_data = _find_clip_sources(
        date=date, selected_segments=selected, clip_root=clip_root_path
    )
    clips = []
    missing_subdirectories = []
    for clip in discovered:
        src_clip = Path(clip["source"])
        dst_clip = save_path_date / clip["clip_name"]
        item = {
            **clip,
            "target": str(dst_clip),
            "copied_subdirs": list(_COPIED_SUBDIRS),
            "sensor_source": str(sensors_src),
            "sensor_target": str(dst_clip / "sensors"),
        }
        clips.append(item)
        for subdir in _COPIED_SUBDIRS:
            src_subdir = src_clip / subdir
            if not src_subdir.is_dir():
                missing_subdirectories.append(
                    {
                        "clip_name": clip["clip_name"],
                        "subdir": subdir,
                        "path": str(src_subdir),
                    }
                )
        if not sensors_src.is_dir():
            missing_subdirectories.append(
                {
                    "clip_name": clip["clip_name"],
                    "subdir": "sensors",
                    "path": str(sensors_src),
                }
            )

    if not clips:
        result = {
            "ok": False,
            "error_type": "no_clip_folders",
            **base,
            "clips": [],
            "missing_sync_data": missing_sync_data,
            "missing_subdirectories": missing_subdirectories,
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message="no VLA clip folders were found under selected sync_data directories",
                data=result,
            )
        return result

    if missing_subdirectories:
        result = {
            "ok": False,
            "error_type": "missing_required_subdirectories",
            **base,
            "clips": clips,
            "clip_count": len(clips),
            "missing_sync_data": missing_sync_data,
            "missing_subdirectories": missing_subdirectories,
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message="one or more required VLA finish dataset inputs are missing",
                data=result,
            )
        return result

    if not dry_run:
        save_path_date.mkdir(parents=True, exist_ok=True)
        for clip in clips:
            src_clip = Path(clip["source"])
            dst_clip = Path(clip["target"])
            dst_clip.mkdir(parents=True, exist_ok=True)
            if sensors_src.is_dir():
                _copy_dir(sensors_src, dst_clip / "sensors")
            for subdir in _COPIED_SUBDIRS:
                src_subdir = src_clip / subdir
                if src_subdir.is_dir():
                    _copy_dir(src_subdir, dst_clip / subdir)

    result = {
        "ok": True,
        **base,
        "clips": clips,
        "clip_count": len(clips),
        "missing_sync_data": missing_sync_data,
        "missing_subdirectories": missing_subdirectories,
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_end",
            ok=True,
            message=(
                "prepared VLA finish dataset"
                if not dry_run
                else "planned VLA finish dataset preparation"
            ),
            data=result,
        )
    return result

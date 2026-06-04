from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.selection import (
    normalize_selected_segments,
    validate_date,
)

ValidationLevel = Literal["clip", "finish", "full"]
_STAGE = "validate_outputs"


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _path_check(path: Path, *, kind: str = "dir") -> dict[str, Any]:
    exists = path.is_file() if kind == "file" else path.is_dir()
    return {"ok": exists, "path": str(path), "kind": kind}


def _clip_sync_data_check(
    *, date: str, clip_root: Path, selected_segments: list[str]
) -> dict[str, Any]:
    segments = []
    missing = []
    for segment in selected_segments:
        sync_data = clip_root / date / segment / "sync_data"
        item = {"segment": segment, "path": str(sync_data), "ok": sync_data.is_dir()}
        segments.append(item)
        if not item["ok"]:
            missing.append(item)
    return {
        "ok": bool(selected_segments) and not missing,
        "selected_segments": selected_segments,
        "segments": segments,
        "missing": missing,
        "count": len([item for item in segments if item["ok"]]),
    }


def _sample_clip_dirs(samples_date_dir: Path) -> list[Path]:
    if not samples_date_dir.is_dir():
        return []
    return sorted(
        [item for item in samples_date_dir.iterdir() if item.is_dir()],
        key=lambda p: p.name,
    )


def _annotation_yaml_check(samples_date_dir: Path) -> dict[str, Any]:
    yaml_paths = sorted(path for path in samples_date_dir.glob("*/*.yaml") if path.is_file())
    clips_without_yaml = []
    for clip_dir in _sample_clip_dirs(samples_date_dir):
        if not any(clip_dir.glob("*.yaml")):
            clips_without_yaml.append(clip_dir.name)
    return {
        "ok": bool(yaml_paths) and not clips_without_yaml,
        "count": len(yaml_paths),
        "paths": [str(path) for path in yaml_paths],
        "clips_without_yaml": clips_without_yaml,
    }


def _tracking_outputs_check(samples_date_dir: Path) -> dict[str, Any]:
    tracking_dirs = sorted(
        path for path in samples_date_dir.glob("*/tracking_img_*") if path.is_dir()
    )
    point_files = sorted(path for path in samples_date_dir.glob("*/img_*.txt") if path.is_file())
    paths = [*tracking_dirs, *point_files]
    return {
        "ok": bool(paths),
        "count": len(paths),
        "tracking_image_dirs": [str(path) for path in tracking_dirs],
        "point_files": [str(path) for path in point_files],
    }


def _is_world_result_txt(path: Path) -> bool:
    name = path.name.lower()
    return (
        path.suffix.lower() == ".txt"
        and "img_" not in name
        and ("master" in name or "other" in name)
    )


def _final_outputs_check(
    *, final_date_dir: Path, samples_date_dir: Path
) -> dict[str, Any]:
    expected_clip_names = [clip_dir.name for clip_dir in _sample_clip_dirs(samples_date_dir)]
    if not expected_clip_names and final_date_dir.is_dir():
        expected_clip_names = sorted(
            [item.name for item in final_date_dir.iterdir() if item.is_dir()]
        )

    gridmap_required = False
    if samples_date_dir.is_dir():
        gridmap_required = any(
            path.is_dir() for path in samples_date_dir.glob("*/grid_map")
        )
    if final_date_dir.is_dir():
        gridmap_required = gridmap_required or any(
            path.is_dir() for path in final_date_dir.glob("*/grid_map")
        )

    clips: dict[str, Any] = {}
    missing_clips = []
    for clip_name in expected_clip_names:
        candidates = sorted(
            [
                path
                for path in final_date_dir.glob(f"*/{clip_name}")
                if path.is_dir()
            ],
            key=lambda path: str(path),
        )
        direct_clip_dir = final_date_dir / clip_name
        if not candidates and direct_clip_dir.is_dir():
            candidates = [direct_clip_dir]
        clip_dir = candidates[0] if candidates else direct_clip_dir
        missing = []
        rout_plot = clip_dir / "rout_plot_v2"
        trajectory_json = clip_dir / f"{clip_name}_trajectory.json"
        speed_direction_json = clip_dir / f"{clip_name}_speed_direction.json"
        world_txt = (
            sorted(
                [
                    path
                    for path in clip_dir.glob("*.txt")
                    if path.is_file() and _is_world_result_txt(path)
                ],
                key=lambda path: path.name,
            )
            if clip_dir.is_dir()
            else []
        )
        grid_map = clip_dir / "grid_map"

        if not clip_dir.is_dir():
            missing.append("final_clip_dir")
        if not rout_plot.is_dir():
            missing.append("rout_plot_v2")
        if not trajectory_json.is_file():
            missing.append("trajectory_json")
        if not speed_direction_json.is_file():
            missing.append("speed_direction_json")
        if not world_txt:
            missing.append("world_result_txt")
        if gridmap_required and not grid_map.is_dir():
            missing.append("grid_map")

        clips[clip_name] = {
            "ok": not missing,
            "path": str(clip_dir),
            "missing": missing,
            "rout_plot_v2": str(rout_plot),
            "trajectory_json": str(trajectory_json),
            "speed_direction_json": str(speed_direction_json),
            "world_result_txt": [str(path) for path in world_txt],
            "grid_map": str(grid_map) if gridmap_required else None,
        }
        if missing:
            missing_clips.append(clip_name)

    return {
        "ok": bool(expected_clip_names) and not missing_clips,
        "final_date_dir": str(final_date_dir),
        "expected_clips": expected_clip_names,
        "missing_clips": missing_clips,
        "gridmap_required": gridmap_required,
        "clips": clips,
        "count": len([item for item in clips.values() if item["ok"]]),
    }


def _suggest_next_action(level: ValidationLevel, checks: dict[str, Any]) -> str:
    if not checks["clip_sync_data"]["ok"]:
        return "run_extract_and_sync"
    if level == "clip":
        return "prepare_finish_dataset"
    if not checks["finish_temp_samples"]["ok"]:
        return "prepare_finish_dataset"
    if level == "finish":
        return "build_noobscenes_inputs"
    if not checks["annotation_yaml"]["ok"]:
        return "run_manual_box_annotation"
    if not checks["tracking_outputs"]["ok"]:
        return "run_tracking"
    if not checks["finish_final"]["ok"] or not checks["final_outputs"]["ok"]:
        return "run_projection_and_trajectory"
    return "pipeline_complete"


def _required_checks(level: ValidationLevel) -> tuple[str, ...]:
    if level == "clip":
        return ("clip_sync_data",)
    if level == "finish":
        return ("clip_sync_data", "finish_temp_samples")
    return (
        "clip_sync_data",
        "finish_temp_samples",
        "finish_final",
        "annotation_yaml",
        "tracking_outputs",
        "final_outputs",
    )


def validate_outputs(
    *,
    date: str,
    clip_root: str,
    finish_root: str,
    selected_segments: list[str],
    level: ValidationLevel = "full",
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    selected = normalize_selected_segments(selected_segments)
    clip_root_path = Path(clip_root).expanduser()
    finish_root_path = Path(finish_root).expanduser()
    finish_temp = finish_root_path / f"{date}_temp"
    finish_final = finish_root_path / date
    samples_date_dir = finish_temp / "samples" / date

    base = {
        "date": date,
        "clip_root": str(clip_root_path),
        "finish_root": str(finish_root_path),
        "selected_segments": selected,
        "level": level,
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
    }
    logger = _logger(log_dir)
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting VLA output validation",
            data=base,
        )

    checks = {
        "clip_sync_data": _clip_sync_data_check(
            date=date, clip_root=clip_root_path, selected_segments=selected
        ),
        "finish_temp_samples": _path_check(samples_date_dir),
        "finish_final": _path_check(finish_final),
        "annotation_yaml": _annotation_yaml_check(samples_date_dir),
        "tracking_outputs": _tracking_outputs_check(samples_date_dir),
        "final_outputs": _final_outputs_check(
            final_date_dir=finish_final,
            samples_date_dir=samples_date_dir,
        ),
    }
    required = _required_checks(level)
    ok = all(bool(checks[name]["ok"]) for name in required)
    result = {
        "ok": ok,
        **base,
        "required_checks": list(required),
        "paths": {
            "finish_temp": str(finish_temp),
            "finish_final": str(finish_final),
            "samples_date_dir": str(samples_date_dir),
        },
        "checks": checks,
        "suggested_next_action": _suggest_next_action(level, checks),
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_end",
            ok=ok,
            message="validated VLA outputs" if ok else "VLA outputs are incomplete",
            data=result,
        )
        logger.write_summary(result)
    return result

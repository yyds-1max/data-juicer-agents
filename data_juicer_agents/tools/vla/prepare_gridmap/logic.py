from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.config import VLARuntime
from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.runtime import python_data_command
from data_juicer_agents.tools.vla._shared.selection import (
    normalize_selected_segments,
    sorted_child_dirs,
    validate_date,
)

_STAGE = "prepare_gridmap"
_CLIP_PREFIXES = ("2025", "2026", "2027")
_GRID_SIZE = 200
_GRID_TRANSFORM = "cp_gridmap_coordinate_transform"


def _runtime(data_python: str, data_env_setup: str | None) -> VLARuntime:
    return VLARuntime(
        data_python=data_python,
        data_env_setup=Path(data_env_setup).expanduser() if data_env_setup else None,
    )


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _default_generator_script(trajectory_root: Path) -> Path:
    return trajectory_root / "other_code" / "pcd_to_grid.py"


def _transform_grid_data(original_data: list[Any]) -> list[Any]:
    original_2d = [
        original_data[i * _GRID_SIZE : (i + 1) * _GRID_SIZE]
        for i in range(_GRID_SIZE)
    ]
    transposed_2d = [list(row) for row in zip(*original_2d)]
    transformed_2d = [row[::-1] for row in transposed_2d]
    return [value for row in transformed_2d for value in row]


def _write_transformed_grid_json(src: Path, dst: Path) -> None:
    data = json.loads(src.read_text(encoding="utf-8"))
    grid_data = data.get("data")
    if not isinstance(grid_data, list) or len(grid_data) != _GRID_SIZE * _GRID_SIZE:
        raise ValueError(f"grid_map JSON data must contain {_GRID_SIZE * _GRID_SIZE} cells: {src}")
    data["data"] = _transform_grid_data(grid_data)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _prepare_gridmap_dir(src: Path, dst: Path) -> dict[str, int]:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    transformed_json = 0
    copied_files = 0
    for item in sorted(src.iterdir(), key=lambda path: path.name):
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target)
            continue
        if item.suffix.lower() == ".json":
            _write_transformed_grid_json(item, target)
            transformed_json += 1
        else:
            shutil.copy2(item, target)
            copied_files += 1
    return {"transformed_json_count": transformed_json, "copied_file_count": copied_files}


def _discover_clip_gridmaps(
    *, date: str, selected_segments: list[str], clip_root: Path, finish_root: Path
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    discovered = []
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
            grid_map = clip_dir / "grid_map"
            if not grid_map.is_dir():
                continue
            target = (
                finish_root
                / f"{date}_temp"
                / "samples"
                / date
                / clip_dir.name
                / "grid_map"
            )
            discovered.append(
                {
                    "segment": segment,
                    "clip_name": clip_dir.name,
                    "source": str(grid_map),
                    "target": str(target),
                    "transform": _GRID_TRANSFORM,
                }
            )
    return discovered, missing_sync_data


def _generator_command(
    *,
    runtime: VLARuntime,
    generator_script: Path,
    clip_root: Path,
    date: str,
    selected_segments: list[str],
) -> list[str]:
    args = [
        "--base-path",
        str(clip_root),
        "--date",
        date,
        "--segments",
        *selected_segments,
    ]
    return python_data_command(runtime, generator_script, args)


def _run_command(
    *, command: list[str], cwd: Path, timeout: int | None, logger: VLARunLogger | None
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or getattr(exc, "output", None) or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode(errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode(errors="replace")
        if logger:
            logger.command(
                stage=f"{_STAGE}:pointcloud_to_gridmap",
                command=command,
                cwd=str(cwd),
                return_code=None,
                stdout=stdout,
                stderr=stderr,
            )
        return {
            "command": command,
            "cwd": str(cwd),
            "return_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "timeout": timeout,
        }

    if logger:
        logger.command(
            stage=f"{_STAGE}:pointcloud_to_gridmap",
            command=command,
            cwd=str(cwd),
            return_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    return {
        "command": command,
        "cwd": str(cwd),
        "return_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _finish(
    logger: VLARunLogger | None,
    result: dict[str, Any],
    message: str,
) -> dict[str, Any]:
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_end",
            ok=bool(result.get("ok")),
            message=message,
            data=result,
        )
        logger.write_summary(result)
    return result


def prepare_gridmap(
    *,
    date: str,
    selected_segments: list[str],
    clip_root: str,
    finish_root: str,
    trajectory_root: str,
    gridmap_variant: str,
    data_env_setup: str | None = None,
    data_python: str = "python3",
    generator_script: str | None = None,
    timeout: int | None = None,
    dry_run: bool = True,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    selected = normalize_selected_segments(selected_segments)
    clip_root_path = Path(clip_root).expanduser()
    finish_root_path = Path(finish_root).expanduser()
    trajectory_root_path = Path(trajectory_root).expanduser()
    generator_path = (
        Path(generator_script).expanduser()
        if generator_script
        else _default_generator_script(trajectory_root_path)
    )
    runtime = _runtime(data_python, data_env_setup)
    command = (
        _generator_command(
            runtime=runtime,
            generator_script=generator_path,
            clip_root=clip_root_path,
            date=date,
            selected_segments=selected,
        )
        if gridmap_variant == "pointcloud_to_gridmap"
        else None
    )
    base = {
        "date": date,
        "selected_segments": selected,
        "clip_root": str(clip_root_path),
        "finish_root": str(finish_root_path),
        "trajectory_root": str(trajectory_root_path),
        "gridmap_variant": gridmap_variant,
        "generator_script": str(generator_path),
        "data_env_setup": data_env_setup,
        "data_python": data_python,
        "timeout": timeout,
        "dry_run": bool(dry_run),
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
        "commands": [command] if command else [],
    }
    logger = _logger(log_dir)
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting VLA gridmap preparation",
            data=base,
        )

    if not selected:
        return _finish(
            logger,
            {**base, "ok": False, "error_type": "no_selected_segments"},
            "no VLA clip segments were selected",
        )

    if gridmap_variant not in {"copy_existing_artifact", "pointcloud_to_gridmap"}:
        raise ValueError(f"unsupported gridmap_variant: {gridmap_variant}")

    command_results = []
    if gridmap_variant == "pointcloud_to_gridmap":
        if not dry_run and not generator_path.is_file():
            return _finish(
                logger,
                {
                    **base,
                    "ok": False,
                    "error_type": "missing_gridmap_generator_script",
                    "path": str(generator_path),
                },
                "VLA pointcloud-to-gridmap generator script is missing",
            )
        if not dry_run and command:
            run_result = _run_command(
                command=command,
                cwd=generator_path.parent,
                timeout=timeout,
                logger=logger,
            )
            command_results.append(run_result)
            if run_result["return_code"] != 0:
                error_type = (
                    "gridmap_generation_timeout"
                    if run_result.get("timed_out")
                    else "gridmap_generation_command_failed"
                )
                return _finish(
                    logger,
                    {
                        **base,
                        "ok": False,
                        "error_type": error_type,
                        "command_results": command_results,
                    },
                    "VLA pointcloud-to-gridmap command failed",
                )

    discovered, missing_sync_data = _discover_clip_gridmaps(
        date=date,
        selected_segments=selected,
        clip_root=clip_root_path,
        finish_root=finish_root_path,
    )
    if gridmap_variant == "copy_existing_artifact" and not discovered:
        return _finish(
            logger,
            {
                **base,
                "ok": False,
                "error_type": "missing_existing_gridmap_artifact",
                "gridmaps": [],
                "missing_sync_data": missing_sync_data,
                "next_actions": [
                    "run pointcloud_to_gridmap variant or inspect clip sync_data"
                ],
            },
            "no existing VLA grid_map artifacts were found",
        )

    transform_results = []
    if not dry_run:
        for item in discovered:
            transform_result = _prepare_gridmap_dir(Path(item["source"]), Path(item["target"]))
            transform_results.append({**item, **transform_result})

    prepared_paths = [item["target"] for item in discovered]
    result = {
        **base,
        "ok": True,
        "gridmaps": discovered,
        "prepared_gridmap_count": len(discovered),
        "prepared_paths": prepared_paths,
        "gridmap_transform": _GRID_TRANSFORM,
        "transform_results": transform_results,
        "missing_sync_data": missing_sync_data,
        "command_results": command_results,
    }
    return _finish(
        logger,
        result,
        (
            "planned VLA gridmap preparation"
            if dry_run
            else "prepared VLA gridmap artifacts"
        ),
    )

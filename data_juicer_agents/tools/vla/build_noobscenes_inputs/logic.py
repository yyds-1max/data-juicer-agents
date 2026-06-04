from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.config import VLARuntime
from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.runtime import python_data_command

_STAGE = "build_noobscenes_inputs"
_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _runtime(data_python: str, data_env_setup: str | None) -> VLARuntime:
    return VLARuntime(
        data_python=data_python,
        data_env_setup=Path(data_env_setup).expanduser() if data_env_setup else None,
    )


def _command_step(name: str, cwd: Path, command: list[str]) -> dict[str, Any]:
    return {"name": name, "cwd": str(cwd), "command": command}


def _has_images(path: Path) -> bool:
    if not path.is_dir():
        return False
    return any(
        item.is_file() and item.suffix.lower() in _IMAGE_SUFFIXES
        for item in path.iterdir()
    )


def _scan_noobscenes_inputs(temp_path: Path) -> dict[str, Any]:
    samples_dir = temp_path / "samples"
    trainval_dir = temp_path / "v1.0-trainval"
    warnings = []
    clips = []
    video_paths = []
    metadata_json_paths = []

    if not samples_dir.is_dir():
        warnings.append({"type": "missing_samples_dir", "path": str(samples_dir)})
    else:
        for date_dir in sorted(
            [item for item in samples_dir.iterdir() if item.is_dir()],
            key=lambda p: p.name,
        ):
            for clip_dir in sorted(
                [item for item in date_dir.iterdir() if item.is_dir()],
                key=lambda p: p.name,
            ):
                fisheye_dir = clip_dir / "fisheye_front"
                point_dir = clip_dir / "r32_rslidar_points"
                clip = {
                    "date": date_dir.name,
                    "clip_name": clip_dir.name,
                    "path": str(clip_dir),
                    "fisheye_front_dir": str(fisheye_dir),
                    "r32_rslidar_points_dir": str(point_dir),
                    "metadata_json_path": str(clip_dir / f"{clip_dir.name}.json"),
                    "video_path": str(clip_dir / "dog.mp4"),
                }
                clips.append(clip)
                metadata_json_paths.append(clip["metadata_json_path"])
                video_paths.append(clip["video_path"])
                if not fisheye_dir.is_dir():
                    warnings.append(
                        {
                            "type": "missing_image_dir",
                            "clip_name": clip_dir.name,
                            "path": str(fisheye_dir),
                        }
                    )
                elif not _has_images(fisheye_dir):
                    warnings.append(
                        {
                            "type": "missing_images",
                            "clip_name": clip_dir.name,
                            "path": str(fisheye_dir),
                        }
                    )
                if not point_dir.is_dir():
                    warnings.append(
                        {
                            "type": "missing_point_dir",
                            "clip_name": clip_dir.name,
                            "path": str(point_dir),
                        }
                    )

    return {
        "clips": clips,
        "generated_metadata_paths": {
            "trainval_dir": str(trainval_dir),
            "maps_dir": str(temp_path / "maps"),
            "map_png": str(temp_path / "maps" / "map.png"),
            "metadata_json_paths": metadata_json_paths,
        },
        "video_paths": video_paths,
        "warnings": warnings,
    }


def build_noobscenes_plan(
    *,
    save_path_temp: str,
    trajectory_root: str,
    data_env_setup: str | None,
    data_python: str,
    dataset_version: str = "v1.0-develop",
) -> dict[str, Any]:
    temp_path = Path(save_path_temp).expanduser()
    trajectory_path = Path(trajectory_root).expanduser()
    runtime = _runtime(data_python, data_env_setup)
    script_specs = [
        (
            "create_box_json",
            trajectory_path / "NoobScenes" / "include" / "0_creat_box.py",
            ["--dataset_root", str(temp_path)],
            trajectory_path / "NoobScenes",
        ),
        (
            "convert_odom",
            trajectory_path / "NoobScenes" / "include" / "1_odom_convert.py",
            ["--temp_path", str(temp_path)],
            trajectory_path / "NoobScenes",
        ),
        (
            "resize_images",
            trajectory_path / "NoobScenes" / "include" / "2_resize.py",
            ["--temp_path", str(temp_path)],
            trajectory_path / "NoobScenes",
        ),
        (
            "build_noobscenes_metadata",
            "./main_smart_odom.py",
            [],
            trajectory_path / "NoobScenes",
        ),
        (
            "generate_tracking_video",
            trajectory_path / "0_1th_box" / "img2video.py",
            ["--dataset_root", str(temp_path)],
            trajectory_path / "0_1th_box",
        ),
    ]
    steps = [
        _command_step(
            name,
            cwd,
            python_data_command(runtime, script, args),
        )
        for name, script, args, cwd in script_specs
    ]
    return {
        "ok": True,
        "save_path_temp": str(temp_path),
        "trajectory_root": str(trajectory_path),
        "data_env_setup": data_env_setup,
        "data_python": data_python,
        "dataset_version": dataset_version,
        **_scan_noobscenes_inputs(temp_path),
        "steps": steps,
        "commands": [step["command"] for step in steps],
        "operations": [
            {
                "name": "link_samples",
                "source": str(temp_path / "samples"),
                "target": str(trajectory_path / "NoobScenes" / "samples"),
            },
            {
                "name": "move_dataset_version",
                "source": str(trajectory_path / "NoobScenes" / dataset_version),
                "target": str(temp_path / "v1.0-trainval"),
            },
            {
                "name": "copy_map",
                "source": str(trajectory_path / "NoobScenes" / "maps" / "map.png"),
                "target": str(temp_path / "maps" / "map.png"),
            },
        ],
    }


def _run_command(
    *,
    stage_name: str,
    command: list[str],
    cwd: str,
    logger: VLARunLogger | None,
) -> dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if logger:
        logger.command(
            stage=f"{_STAGE}:{stage_name}",
            command=command,
            cwd=cwd,
            return_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    return {
        "name": stage_name,
        "command": command,
        "cwd": cwd,
        "return_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _prepare_main_smart_odom_workspace(plan: dict[str, Any]) -> dict[str, Any] | None:
    samples_src = Path(plan["save_path_temp"]) / "samples"
    samples_link = Path(plan["trajectory_root"]) / "NoobScenes" / "samples"
    trainval = Path(plan["save_path_temp"]) / "v1.0-trainval"
    trainval.mkdir(parents=True, exist_ok=True)
    if samples_link.is_symlink() or samples_link.is_file():
        samples_link.unlink()
    elif samples_link.exists():
        return {
            "ok": False,
            "error_type": "samples_path_exists_not_symlink",
            "path": str(samples_link),
        }
    samples_link.symlink_to(samples_src, target_is_directory=True)
    return None


def _move_dataset_version(plan: dict[str, Any]) -> dict[str, Any] | None:
    noobscenes_root = Path(plan["trajectory_root"]) / "NoobScenes"
    source = noobscenes_root / plan["dataset_version"]
    target = Path(plan["save_path_temp"]) / "v1.0-trainval"
    if not source.is_dir():
        return {
            "ok": False,
            "error_type": "missing_dataset_version",
            "path": str(source),
        }
    target.mkdir(parents=True, exist_ok=True)
    for item in target.iterdir():
        if item.is_dir() and not item.is_symlink():
            shutil.rmtree(item)
        else:
            item.unlink()
    for item in source.iterdir():
        shutil.move(str(item), str(target / item.name))
    return None


def _copy_map(plan: dict[str, Any]) -> dict[str, Any] | None:
    source = Path(plan["trajectory_root"]) / "NoobScenes" / "maps" / "map.png"
    target = Path(plan["save_path_temp"]) / "maps" / "map.png"
    if target.exists():
        return None
    if not source.is_file():
        return {"ok": False, "error_type": "missing_map", "path": str(source)}
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return None


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
    return result


def _blocking_input_warnings(plan: dict[str, Any]) -> list[dict[str, str]]:
    blocking_types = {
        "missing_samples_dir",
        "missing_image_dir",
        "missing_images",
        "missing_point_dir",
    }
    return [item for item in plan["warnings"] if item["type"] in blocking_types]


def _required_legacy_paths(plan: dict[str, Any]) -> list[dict[str, str]]:
    trajectory_root = Path(plan["trajectory_root"])
    noobscenes = trajectory_root / "NoobScenes"
    noobscenes_include = noobscenes / "include"
    video_root = trajectory_root / "0_1th_box"
    return [
        {"type": "cwd", "name": "NoobScenes", "path": str(noobscenes)},
        {"type": "dir", "name": "NoobScenes/include", "path": str(noobscenes_include)},
        {
            "type": "script",
            "name": "0_creat_box.py",
            "path": str(noobscenes_include / "0_creat_box.py"),
        },
        {
            "type": "script",
            "name": "1_odom_convert.py",
            "path": str(noobscenes_include / "1_odom_convert.py"),
        },
        {
            "type": "script",
            "name": "2_resize.py",
            "path": str(noobscenes_include / "2_resize.py"),
        },
        {
            "type": "script",
            "name": "main_smart_odom.py",
            "path": str(noobscenes / "main_smart_odom.py"),
        },
        {"type": "cwd", "name": "0_1th_box", "path": str(video_root)},
        {
            "type": "script",
            "name": "img2video.py",
            "path": str(video_root / "img2video.py"),
        },
    ]


def _missing_legacy_paths(plan: dict[str, Any]) -> list[dict[str, str]]:
    missing = []
    for item in _required_legacy_paths(plan):
        path = Path(item["path"])
        if item["type"] in {"cwd", "dir"}:
            exists = path.is_dir()
        else:
            exists = path.is_file()
        if not exists:
            missing.append(item)
    return missing


def build_noobscenes_inputs(
    *,
    save_path_temp: str,
    trajectory_root: str,
    data_env_setup: str | None,
    data_python: str,
    dataset_version: str = "v1.0-develop",
    dry_run: bool = True,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    plan = build_noobscenes_plan(
        save_path_temp=save_path_temp,
        trajectory_root=trajectory_root,
        data_env_setup=data_env_setup,
        data_python=data_python,
        dataset_version=dataset_version,
    )
    plan.update(
        {
            "dry_run": bool(dry_run),
            "run_id": run_id,
            "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
        }
    )
    logger = _logger(log_dir)
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting NoobScenes input preparation",
            data=plan,
        )

    if dry_run:
        return _finish(logger, plan, "planned NoobScenes input preparation")

    blocking_warnings = _blocking_input_warnings(plan)
    if blocking_warnings or not plan["clips"]:
        return _finish(
            logger,
            {
                **plan,
                "ok": False,
                "error_type": "noobscenes_input_validation_failed",
                "blocking_warnings": blocking_warnings,
            },
            "NoobScenes input validation failed",
        )

    missing_legacy_paths = _missing_legacy_paths(plan)
    if missing_legacy_paths:
        return _finish(
            logger,
            {
                **plan,
                "ok": False,
                "error_type": "missing_legacy_paths",
                "missing": missing_legacy_paths,
            },
            "NoobScenes legacy cwd or script paths are missing",
        )

    command_results = []
    first_three = plan["steps"][:3]
    for step in first_three:
        result = _run_command(
            stage_name=step["name"],
            command=step["command"],
            cwd=step["cwd"],
            logger=logger,
        )
        command_results.append(result)
        if result["return_code"] != 0:
            failure = {
                **plan,
                "ok": False,
                "error_type": "noobscenes_command_failed",
                "failed_step": step["name"],
                "command_results": command_results,
            }
            return _finish(logger, failure, "NoobScenes preprocessing command failed")

    workspace_error = _prepare_main_smart_odom_workspace(plan)
    if workspace_error:
        return _finish(
            logger,
            {
                **plan,
                **workspace_error,
                "ok": False,
                "command_results": command_results,
            },
            "NoobScenes workspace preparation failed",
        )

    metadata_step = plan["steps"][3]
    metadata_result = _run_command(
        stage_name=metadata_step["name"],
        command=metadata_step["command"],
        cwd=metadata_step["cwd"],
        logger=logger,
    )
    command_results.append(metadata_result)
    if metadata_result["return_code"] != 0:
        return _finish(
            logger,
            {
                **plan,
                "ok": False,
                "error_type": "noobscenes_command_failed",
                "failed_step": metadata_step["name"],
                "command_results": command_results,
            },
            "NoobScenes metadata generation command failed",
        )

    move_error = _move_dataset_version(plan)
    if move_error:
        return _finish(
            logger,
            {**plan, **move_error, "ok": False, "command_results": command_results},
            "NoobScenes generated metadata movement failed",
        )
    map_error = _copy_map(plan)
    if map_error:
        return _finish(
            logger,
            {**plan, **map_error, "ok": False, "command_results": command_results},
            "NoobScenes map copy failed",
        )

    video_step = plan["steps"][4]
    video_result = _run_command(
        stage_name=video_step["name"],
        command=video_step["command"],
        cwd=video_step["cwd"],
        logger=logger,
    )
    command_results.append(video_result)
    result = {
        **plan,
        "ok": video_result["return_code"] == 0,
        "command_results": command_results,
    }
    if not result["ok"]:
        result["error_type"] = "noobscenes_command_failed"
        result["failed_step"] = video_step["name"]
    return _finish(
        logger,
        result,
        (
            "prepared NoobScenes inputs"
            if result["ok"]
            else "NoobScenes video generation failed"
        ),
    )

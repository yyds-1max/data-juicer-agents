from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.config import VLARuntime
from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.runtime import python_data_command

_STAGE = "run_projection_and_trajectory"


def _runtime(data_python: str, data_env_setup: str | None) -> VLARuntime:
    return VLARuntime(
        data_python=data_python,
        data_env_setup=Path(data_env_setup).expanduser() if data_env_setup else None,
    )


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _step(name: str, cwd: Path, script: Path, command: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "cwd": str(cwd),
        "script": str(script),
        "command": command,
    }


def _planned_outputs(save_path: Path, save_path_temp: Path) -> dict[str, list[str]]:
    return {
        "generated_projection_files": [
            str(save_path_temp / "samples" / "*" / "*" / "project_npy" / "*"),
            str(save_path_temp / "samples" / "*" / "*" / "*project*.npy"),
        ],
        "world_coordinate_files": [
            str(save_path_temp / "samples" / "*" / "*" / "*master*.txt"),
            str(save_path_temp / "samples" / "*" / "*" / "*other*.txt"),
        ],
        "speed_direction_outputs": [
            str(save_path_temp / "samples" / "*" / "*" / "*speed_direction*.json"),
            str(save_path / "*" / "*" / "*speed_direction*.json"),
        ],
        "trajectory_outputs": [str(save_path / "*" / "*" / "*_trajectory.json")],
        "moved_final_result_paths": [
            str(save_path / "*" / "*"),
            str(save_path / "*" / "*" / "rout_plot_v2"),
            str(save_path / "*" / "*" / "*.txt"),
            str(save_path / "*" / "*" / "*.json"),
        ],
    }


def _is_world_result_txt(path: Path) -> bool:
    name = path.name.lower()
    return (
        path.suffix.lower() == ".txt"
        and "img_" not in name
        and ("master" in name or "other" in name)
    )


def _sorted_existing(paths: list[Path]) -> list[str]:
    return [str(path) for path in sorted(paths, key=lambda item: str(item))]


def _scan_output_paths(save_path: str, save_path_temp: str) -> dict[str, list[str]]:
    final_path = Path(save_path)
    temp_path = Path(save_path_temp)
    projection_files = []
    samples_root = temp_path / "samples"
    if samples_root.is_dir():
        projection_files.extend(
            path for path in samples_root.glob("*/*/project_npy/*") if path.is_file()
        )
        projection_files.extend(
            path for path in samples_root.glob("*/*/*project*.npy") if path.is_file()
        )

    temp_world_files = [
        path
        for path in samples_root.glob("*/*/*.txt")
        if path.is_file() and _is_world_result_txt(path)
    ]
    final_world_files = [
        path
        for path in final_path.glob("*/*/*.txt")
        if path.is_file() and _is_world_result_txt(path)
    ]
    temp_speed = [
        path
        for path in samples_root.glob("*/*/*speed_direction*.json")
        if path.is_file()
    ]
    final_speed = [
        path
        for path in final_path.glob("*/*/*speed_direction*.json")
        if path.is_file()
    ]
    trajectory_outputs = [
        path for path in final_path.glob("*/*/*_trajectory.json") if path.is_file()
    ]
    moved_paths = []
    if final_path.is_dir():
        moved_paths.extend(path for path in final_path.glob("*/*") if path.is_dir())
        moved_paths.extend(
            path
            for path in final_path.glob("*/*/*")
            if path.is_file() and not path.name.startswith(".")
        )
        moved_paths.extend(
            path for path in final_path.glob("*/*/rout_plot_v2") if path.is_dir()
        )

    return {
        "generated_projection_files": _sorted_existing(projection_files),
        "world_coordinate_files": _sorted_existing(temp_world_files)
        + _sorted_existing(final_world_files),
        "speed_direction_outputs": _sorted_existing(temp_speed)
        + _sorted_existing(final_speed),
        "trajectory_outputs": _sorted_existing(trajectory_outputs),
        "moved_final_result_paths": _sorted_existing(moved_paths),
    }


def build_projection_trajectory_plan(
    *,
    save_path: str,
    save_path_temp: str,
    trajectory_root: str,
    data_env_setup: str | None,
    data_python: str = "python3",
    use_gridmap: bool = False,
) -> dict[str, Any]:
    save_path_value = str(Path(save_path).expanduser())
    temp_path = Path(save_path_temp).expanduser()
    trajectory_path = Path(trajectory_root).expanduser()
    runtime = _runtime(data_python, data_env_setup)
    project_root = trajectory_path / "NuscenesAanlysis_smart_pts_project"
    pt_project_root = trajectory_path / "2_pt_project"

    specs: list[tuple[str, Path, Path, list[str]]] = [
        (
            "project_points",
            project_root,
            project_root / "main.py",
            ["--data_root", str(temp_path)],
        ),
        (
            "image_to_world",
            pt_project_root,
            pt_project_root / "0_img2world.py",
            [str(temp_path)],
        ),
        (
            "speed_direction_odom",
            pt_project_root,
            pt_project_root / "4_speed_direction_odom.py",
            [str(temp_path)],
        ),
        (
            "generate_trajectory",
            pt_project_root,
            pt_project_root / "2_othermethod_cjl.py",
            [str(temp_path)],
        ),
        (
            "move_results",
            pt_project_root,
            pt_project_root / "3_move_dir.py",
            ["--root_path", save_path_value, "--temp_path", str(temp_path)],
        ),
    ]
    if use_gridmap:
        specs.insert(
            3,
            (
                "copy_gridmap",
                trajectory_path / "other_code",
                trajectory_path / "other_code" / "cp_gridmap.py",
                ["--root_data", str(temp_path)],
            ),
        )

    steps = [
        _step(name, cwd, script, python_data_command(runtime, script, args))
        for name, cwd, script, args in specs
    ]
    return {
        "ok": True,
        "save_path": save_path_value,
        "save_path_temp": str(temp_path),
        "trajectory_root": str(trajectory_path),
        "data_env_setup": data_env_setup,
        "data_python": data_python,
        "use_gridmap": bool(use_gridmap),
        "steps": steps,
        "commands": [step["command"] for step in steps],
        "planned_outputs": _planned_outputs(Path(save_path_value), temp_path),
        "output_paths": _planned_outputs(Path(save_path_value), temp_path),
    }


def _required_paths(plan: dict[str, Any]) -> list[dict[str, str]]:
    required = []
    for step in plan["steps"]:
        required.append({"type": "cwd", "name": step["name"], "path": step["cwd"]})
        required.append(
            {"type": "script", "name": step["name"], "path": step["script"]}
        )
    return required


def _missing_required_paths(plan: dict[str, Any]) -> list[dict[str, str]]:
    missing = []
    for item in _required_paths(plan):
        path = Path(item["path"])
        exists = path.is_dir() if item["type"] == "cwd" else path.is_file()
        if not exists:
            missing.append(item)
    return missing


def _run_step(
    *, step: dict[str, Any], timeout: int | None, logger: VLARunLogger | None
) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            step["command"],
            cwd=step["cwd"],
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
                stage=f"{_STAGE}:{step['name']}",
                command=step["command"],
                cwd=step["cwd"],
                return_code=None,
                stdout=stdout,
                stderr=stderr,
            )
        return {
            "name": step["name"],
            "command": step["command"],
            "cwd": step["cwd"],
            "return_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "timeout": timeout,
        }

    if logger:
        logger.command(
            stage=f"{_STAGE}:{step['name']}",
            command=step["command"],
            cwd=step["cwd"],
            return_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    return {
        "name": step["name"],
        "command": step["command"],
        "cwd": step["cwd"],
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


def run_projection_and_trajectory(
    *,
    save_path: str,
    save_path_temp: str,
    trajectory_root: str,
    data_env_setup: str | None,
    data_python: str = "python3",
    use_gridmap: bool = False,
    timeout: int | None = None,
    dry_run: bool = True,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    plan = build_projection_trajectory_plan(
        save_path=save_path,
        save_path_temp=save_path_temp,
        trajectory_root=trajectory_root,
        data_env_setup=data_env_setup,
        data_python=data_python,
        use_gridmap=use_gridmap,
    )
    plan.update(
        {
            "timeout": timeout,
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
            message="starting VLA projection and trajectory",
            data=plan,
        )
    if dry_run:
        return _finish(logger, plan, "planned VLA projection and trajectory")

    if not Path(plan["save_path_temp"]).is_dir():
        return _finish(
            logger,
            {
                **plan,
                "ok": False,
                "error_type": "missing_save_path_temp",
                "path": plan["save_path_temp"],
            },
            "VLA temporary finish dataset is missing",
        )

    missing = _missing_required_paths(plan)
    if missing:
        return _finish(
            logger,
            {
                **plan,
                "ok": False,
                "error_type": "missing_legacy_paths",
                "missing": missing,
            },
            "VLA projection legacy cwd or script paths are missing",
        )

    command_results = []
    for step in plan["steps"]:
        result = _run_step(step=step, timeout=timeout, logger=logger)
        command_results.append(result)
        if result["return_code"] != 0:
            error_type = (
                "projection_trajectory_timeout"
                if result.get("timed_out")
                else "projection_trajectory_command_failed"
            )
            return _finish(
                logger,
                {
                    **plan,
                    "ok": False,
                    "error_type": error_type,
                    "failed_step": step["name"],
                    "command_results": command_results,
                },
                "VLA projection and trajectory command failed",
            )

    output_paths = _scan_output_paths(plan["save_path"], plan["save_path_temp"])
    return _finish(
        logger,
        {
            **plan,
            "ok": True,
            "command_results": command_results,
            "output_paths": output_paths,
            **output_paths,
        },
        "completed VLA projection and trajectory",
    )

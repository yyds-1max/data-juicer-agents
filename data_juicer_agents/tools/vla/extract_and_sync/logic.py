from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.config import VLAPaths, VLARuntime
from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.runtime import run_u_python_command
from data_juicer_agents.tools.vla._shared.selection import (
    normalize_selected_segments,
    validate_date,
)

EXTRACT_SCRIPT = "1_extract_data_from_bag_multi_process_ros2_U.py"
SYNC_SCRIPT = "2_sync_data_multi_process_U.py"
_STAGE = "extract_and_sync"


def _runtime(data_python: str, data_env_setup: str | None) -> VLARuntime:
    setup = Path(data_env_setup).expanduser() if data_env_setup else None
    return VLARuntime(data_python=data_python, data_env_setup=setup)


def _paths(
    raw_root: str,
    clip_root: str,
    data_toolbox_src: str,
    gt_dog_root: str | None = None,
) -> VLAPaths:
    kwargs = {
        "raw_root": Path(raw_root).expanduser(),
        "clip_root": Path(clip_root).expanduser(),
        "data_toolbox_src": Path(data_toolbox_src).expanduser(),
    }
    if gt_dog_root is not None:
        kwargs["gt_dog_root"] = Path(gt_dog_root).expanduser()
    return VLAPaths(**kwargs)


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def build_extract_sync_plan(
    *,
    date: str,
    selected_segments: list[str],
    raw_root: str,
    clip_root: str,
    data_toolbox_src: str,
    data_env_setup: str | None,
    data_python: str,
    processes_num: int,
    query_dir: str,
    sync_output_dir: str,
    sequence_suffix: str,
    gt_dog_root: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    date = validate_date(date)
    runtime = _runtime(data_python, data_env_setup)
    paths = _paths(raw_root, clip_root, data_toolbox_src, gt_dog_root)
    extra_env_value = {str(key): str(value) for key, value in (extra_env or {}).items()}
    segments = []

    for segment in normalize_selected_segments(selected_segments):
        raw_segment = paths.raw_temp_dir(date) / segment
        save_path = paths.clip_date_dir(date) / segment
        sequence_prefix = f"{segment}_{sequence_suffix}"
        extract_cmd = run_u_python_command(
            runtime,
            paths,
            EXTRACT_SCRIPT,
            [
                "--data_path",
                str(raw_segment),
                "--save_path",
                str(save_path),
                "--processes_num",
                str(processes_num),
            ],
        )
        sync_cmd = run_u_python_command(
            runtime,
            paths,
            SYNC_SCRIPT,
            [
                "--data_path",
                str(save_path),
                "--query_dir",
                query_dir,
                "--output_dir",
                sync_output_dir,
                "--sequence_prefix",
                sequence_prefix,
                "--processes_num",
                str(processes_num),
            ],
        )
        segments.append(
            {
                "name": segment,
                "raw_segment": str(raw_segment),
                "save_path": str(save_path),
                "sync_output_dir": sync_output_dir,
                "sequence_prefix": sequence_prefix,
                "commands": [extract_cmd, sync_cmd],
            }
        )

    return {
        "ok": True,
        "date": date,
        "selected_segments": [segment["name"] for segment in segments],
        "segments": segments,
        "cwd": str(paths.data_toolbox_src),
        "data_toolbox_src": str(paths.data_toolbox_src),
        "raw_root": str(paths.raw_root),
        "clip_root": str(paths.clip_root),
        "gt_dog_root": str(paths.gt_dog_root),
        "extra_env": extra_env_value,
    }


def _run_command(
    command: list[str],
    cwd: str,
    extra_env: dict[str, str],
    logger: VLARunLogger | None,
) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(extra_env)
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    if logger:
        logger.command(
            stage=_STAGE,
            command=command,
            cwd=cwd,
            return_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    return {
        "command": command,
        "return_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def _base_payload(
    *,
    date: str,
    selected_segments: list[str],
    raw_root: str,
    clip_root: str,
    data_toolbox_src: str,
    data_env_setup: str | None,
    data_python: str,
    processes_num: int,
    query_dir: str,
    sync_output_dir: str,
    sequence_suffix: str,
    gt_dog_root: str | None,
    extra_env: dict[str, str] | None,
    dry_run: bool,
    run_id: str | None,
    log_dir: str | None,
) -> dict[str, Any]:
    paths = _paths(raw_root, clip_root, data_toolbox_src, gt_dog_root)
    return {
        "date": date,
        "selected_segments": selected_segments,
        "raw_root": str(paths.raw_root),
        "clip_root": str(paths.clip_root),
        "data_toolbox_src": str(paths.data_toolbox_src),
        "data_env_setup": data_env_setup,
        "data_python": data_python,
        "processes_num": processes_num,
        "query_dir": query_dir,
        "sync_output_dir": sync_output_dir,
        "sequence_suffix": sequence_suffix,
        "gt_dog_root": str(paths.gt_dog_root),
        "extra_env": {str(key): str(value) for key, value in (extra_env or {}).items()},
        "dry_run": dry_run,
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
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


def extract_and_sync(**kwargs: Any) -> dict[str, Any]:
    dry_run = bool(kwargs.pop("dry_run", False))
    run_id = kwargs.pop("run_id", None)
    log_dir = kwargs.pop("log_dir", None)
    gt_dog_root = kwargs.get("gt_dog_root")
    extra_env = kwargs.get("extra_env") or {}
    date = validate_date(kwargs["date"])
    selected_segments = normalize_selected_segments(kwargs["selected_segments"])
    base = _base_payload(
        date=date,
        selected_segments=selected_segments,
        raw_root=kwargs["raw_root"],
        clip_root=kwargs["clip_root"],
        data_toolbox_src=kwargs["data_toolbox_src"],
        data_env_setup=kwargs["data_env_setup"],
        data_python=kwargs["data_python"],
        processes_num=kwargs["processes_num"],
        query_dir=kwargs["query_dir"],
        sync_output_dir=kwargs["sync_output_dir"],
        sequence_suffix=kwargs["sequence_suffix"],
        gt_dog_root=gt_dog_root,
        extra_env=extra_env,
        dry_run=dry_run,
        run_id=run_id,
        log_dir=log_dir,
    )
    logger = _logger(log_dir)
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting VLA extract and sync",
            data=base,
        )

    if not selected_segments:
        return _finish(
            logger,
            {"ok": False, "error_type": "no_selected_segments", **base},
            "no VLA segments were selected for extract and sync",
        )

    data_toolbox_src = Path(base["data_toolbox_src"])
    if not data_toolbox_src.is_dir():
        return _finish(
            logger,
            {"ok": False, "error_type": "missing_data_toolbox_src", **base},
            "DataToolbox source directory is missing",
        )

    paths = _paths(
        kwargs["raw_root"],
        kwargs["clip_root"],
        kwargs["data_toolbox_src"],
        gt_dog_root,
    )
    missing = [
        segment
        for segment in selected_segments
        if not (paths.raw_temp_dir(date) / segment).is_dir()
    ]
    if missing:
        return _finish(
            logger,
            {
                "ok": False,
                "error_type": "missing_raw_segments",
                "missing_raw_segments": missing,
                **base,
            },
            "one or more raw temp VLA segments are missing",
        )

    plan = build_extract_sync_plan(**kwargs)
    plan.update(
        {
            "dry_run": dry_run,
            "run_id": run_id,
            "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
        }
    )
    if dry_run or not plan.get("ok"):
        return _finish(
            logger,
            plan,
            (
                "planned VLA extract and sync"
                if dry_run
                else "VLA extract and sync plan failed"
            ),
        )

    completed = []
    for segment in plan["segments"]:
        Path(segment["save_path"]).mkdir(parents=True, exist_ok=True)
        command_results = []
        for index, command in enumerate(segment["commands"]):
            result = _run_command(command, plan["cwd"], plan["extra_env"], logger)
            command_results.append(result)
            if result["return_code"] != 0:
                segment["command_results"] = command_results
                return _finish(
                    logger,
                    {
                        "ok": False,
                        "error_type": "extract_sync_failed",
                        "date": plan["date"],
                        "failed_segment": segment["name"],
                        "failed_command_index": index,
                        "command": command,
                        "stdout": result["stdout"],
                        "stderr": result["stderr"],
                        "completed_segments": completed,
                        "segments": plan["segments"],
                        "dry_run": dry_run,
                        "run_id": run_id,
                        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
                        "data_toolbox_src": plan["data_toolbox_src"],
                        "raw_root": plan["raw_root"],
                        "clip_root": plan["clip_root"],
                        "gt_dog_root": plan["gt_dog_root"],
                        "extra_env": plan["extra_env"],
                    },
                    "VLA extract and sync command failed",
                )
        segment["command_results"] = command_results
        completed.append(segment["name"])

    return _finish(
        logger,
        {
            "ok": True,
            "date": plan["date"],
            "completed_segments": completed,
            "segments": plan["segments"],
            "dry_run": dry_run,
            "run_id": run_id,
            "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
            "data_toolbox_src": plan["data_toolbox_src"],
            "raw_root": plan["raw_root"],
            "clip_root": plan["clip_root"],
            "gt_dog_root": plan["gt_dog_root"],
            "extra_env": plan["extra_env"],
        },
        "completed VLA extract and sync",
    )

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.config import VLARuntime
from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.runtime import data_runtime_command

_STAGE = "run_tracking"


class _TrackingOutputPrepareError(Exception):
    def __init__(self, path: Path, exc: OSError) -> None:
        super().__init__(str(exc))
        self.path = path


def _runtime(data_python: str, data_env_setup: str | None) -> VLARuntime:
    return VLARuntime(
        data_python=data_python,
        data_env_setup=Path(data_env_setup).expanduser() if data_env_setup else None,
    )


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _yaml_files(save_path_temp: Path) -> list[Path]:
    samples_root = save_path_temp / "samples"
    if not samples_root.is_dir():
        return []
    return sorted(path for path in samples_root.glob("*/*/*.yaml") if path.is_file())


def _suffix_from_yaml(yaml_path: Path) -> dict[str, str]:
    parts = yaml_path.stem.split("_", 1)
    identity = parts[0]
    colors = parts[1] if len(parts) > 1 else ""
    suffix = f"{identity}_{colors}" if colors else identity
    return {"identity": identity, "colors": colors, "suffix": suffix}


def build_tracking_plan(
    *,
    save_path_temp: str,
    trajectory_root: str,
    data_env_setup: str | None,
    data_python: str = "python3",
) -> dict[str, Any]:
    temp_path = Path(save_path_temp).expanduser()
    trajectory_path = Path(trajectory_root).expanduser()
    runtime = _runtime(data_python, data_env_setup)
    tracking_cwd = trajectory_path / "1_onnx_tam"
    dog_yaml = trajectory_path / "Data" / "3_param" / "dog.yaml"
    output_root = trajectory_path / "Data" / "1_img_output"
    command = data_runtime_command(runtime, ["./bin/main"])
    jobs = []

    for yaml_path in _yaml_files(temp_path):
        clip_dir = yaml_path.parent
        suffix = _suffix_from_yaml(yaml_path)
        jobs.append(
            {
                "yaml_path": str(yaml_path),
                "clip_dir": str(clip_dir),
                "identity": suffix["identity"],
                "colors": suffix["colors"],
                "copy_yaml": {
                    "source": str(yaml_path),
                    "target": str(dog_yaml),
                },
                "cwd": str(tracking_cwd),
                "command": command,
                "move_outputs": [
                    {
                        "source": str(output_root / "tracking_img"),
                        "target": str(clip_dir / f"tracking_img_{suffix['suffix']}"),
                        "kind": "dir",
                    },
                    {
                        "source": str(output_root / "img_points.txt"),
                        "target": str(clip_dir / f"img_{suffix['suffix']}.txt"),
                        "kind": "file",
                    },
                ],
            }
        )

    result = {
        "ok": bool(jobs),
        "save_path_temp": str(temp_path),
        "trajectory_root": str(trajectory_path),
        "data_env_setup": data_env_setup,
        "data_python": data_python,
        "tracking_jobs": jobs,
        "yaml_count": len(jobs),
    }
    if not jobs:
        result["error_type"] = "no_tracking_yaml"
        result["message"] = "No annotation YAML files were found for tracking."
    return result


def _finish(
    logger: VLARunLogger | None, result: dict[str, Any], message: str
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


def _replace_path(src: Path, dst: Path, kind: str) -> bool:
    if not src.exists():
        return False
    if dst.exists():
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return True


def _delete_existing_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _prepare_tracking_output(output_root: Path) -> None:
    tracking_img = output_root / "tracking_img"
    img_points = output_root / "img_points.txt"

    for path, action in (
        (output_root, lambda: output_root.mkdir(parents=True, exist_ok=True)),
        (tracking_img, lambda: _delete_existing_path(tracking_img)),
        (img_points, lambda: _delete_existing_path(img_points)),
        (tracking_img, lambda: tracking_img.mkdir(parents=True, exist_ok=False)),
    ):
        try:
            action()
        except OSError as exc:
            raise _TrackingOutputPrepareError(path, exc) from exc


def _text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def run_tracking(
    *,
    save_path_temp: str,
    trajectory_root: str,
    data_env_setup: str | None,
    data_python: str = "python3",
    cuda_env: dict[str, str] | None = None,
    extra_env: dict[str, str] | None = None,
    timeout: int | None = None,
    dry_run: bool = True,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    plan = build_tracking_plan(
        save_path_temp=save_path_temp,
        trajectory_root=trajectory_root,
        data_env_setup=data_env_setup,
        data_python=data_python,
    )
    plan.update(
        {
            "cuda_env": {str(k): str(v) for k, v in (cuda_env or {}).items()},
            "extra_env": {str(k): str(v) for k, v in (extra_env or {}).items()},
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
            message="starting VLA tracking",
            data=plan,
        )
    if dry_run or not plan["ok"]:
        return _finish(
            logger,
            plan,
            "planned VLA tracking" if plan["ok"] else "no tracking YAML files found",
        )

    tracking_cwd = Path(plan["trajectory_root"]) / "1_onnx_tam"
    binary = tracking_cwd / "bin" / "main"
    if not tracking_cwd.is_dir() or not binary.is_file():
        return _finish(
            logger,
            {
                **plan,
                "ok": False,
                "error_type": "missing_tracking_binary",
                "missing": [
                    {"type": "cwd", "path": str(tracking_cwd)},
                    {"type": "binary", "path": str(binary)},
                ],
            },
            "tracking binary path is missing",
        )

    env = os.environ.copy()
    env.update(plan["cuda_env"])
    env.update(plan["extra_env"])
    command_results = []
    completed_jobs = []
    failed_yaml_paths = []
    for job in plan["tracking_jobs"]:
        yaml_path = Path(job["yaml_path"])
        output_root = Path(job["move_outputs"][0]["source"]).parent
        try:
            _prepare_tracking_output(output_root)
        except _TrackingOutputPrepareError as exc:
            failed_yaml_paths.append(str(yaml_path))
            return _finish(
                logger,
                {
                    **plan,
                    "ok": False,
                    "error_type": "tracking_output_prepare_failed",
                    "yaml_path": str(yaml_path),
                    "path": str(exc.path),
                    "message": str(exc),
                    "command_results": command_results,
                    "completed_jobs": completed_jobs,
                    "failed_yaml_paths": failed_yaml_paths,
                },
                "failed to prepare VLA tracking output directory",
            )
        dog_yaml = Path(job["copy_yaml"]["target"])
        dog_yaml.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(yaml_path, dog_yaml)

        try:
            proc = subprocess.run(
                job["command"],
                cwd=job["cwd"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=timeout,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = _text(getattr(exc, "stdout", None) or getattr(exc, "output", None))
            stderr = _text(getattr(exc, "stderr", None))
            if logger:
                logger.command(
                    stage=_STAGE,
                    command=job["command"],
                    cwd=job["cwd"],
                    return_code=None,
                    stdout=stdout,
                    stderr=stderr,
                )
            command_results.append(
                {
                    "yaml_path": str(yaml_path),
                    "return_code": None,
                    "stdout": stdout,
                    "stderr": stderr,
                    "timed_out": True,
                    "timeout": timeout,
                    "moved_outputs": [],
                }
            )
            failed_yaml_paths.append(str(yaml_path))
            return _finish(
                logger,
                {
                    **plan,
                    "ok": False,
                    "error_type": "tracking_timeout",
                    "command_results": command_results,
                    "completed_jobs": completed_jobs,
                    "failed_yaml_paths": failed_yaml_paths,
                    "timed_out_yaml_path": str(yaml_path),
                },
                "VLA tracking command timed out",
            )
        if logger:
            logger.command(
                stage=_STAGE,
                command=job["command"],
                cwd=job["cwd"],
                return_code=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
            )
        moved_outputs = []
        for move in job["move_outputs"]:
            moved_outputs.append(
                {
                    **move,
                    "moved": _replace_path(
                        Path(move["source"]), Path(move["target"]), move["kind"]
                    ),
                }
            )
        command_result = {
            "yaml_path": str(yaml_path),
            "return_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "moved_outputs": moved_outputs,
        }
        command_results.append(command_result)
        if proc.returncode == 0 and all(item["moved"] for item in moved_outputs):
            completed_jobs.append(job)
        else:
            failed_yaml_paths.append(str(yaml_path))

    result = {
        **plan,
        "ok": not failed_yaml_paths,
        "command_results": command_results,
        "completed_jobs": completed_jobs,
        "failed_yaml_paths": failed_yaml_paths,
    }
    if failed_yaml_paths:
        result["error_type"] = "tracking_failed"
    return _finish(
        logger,
        result,
        (
            "completed VLA tracking"
            if result["ok"]
            else "one or more tracking jobs failed"
        ),
    )

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.config import VLARuntime
from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.runtime import python_data_command

_STAGE = "run_manual_box_annotation"
_YAML_PATTERNS = ("master_*.yaml", "other*.yaml")


def _runtime(data_python: str, data_env_setup: str | None) -> VLARuntime:
    return VLARuntime(
        data_python=data_python,
        data_env_setup=Path(data_env_setup).expanduser() if data_env_setup else None,
    )


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _clip_dirs(samples_root: Path) -> list[Path]:
    if not samples_root.is_dir():
        return []
    return sorted(
        [
            item
            for date_dir in samples_root.iterdir()
            if date_dir.is_dir()
            for item in date_dir.iterdir()
            if item.is_dir()
        ],
        key=lambda p: (p.parent.name, p.name),
    )


def _yaml_files(clip_dir: Path) -> list[Path]:
    found: list[Path] = []
    for pattern in _YAML_PATTERNS:
        found.extend(clip_dir.glob(pattern))
    return sorted({path.resolve(): path for path in found if path.is_file()}.values())


def build_annotation_command(
    *,
    save_path_temp: str,
    trajectory_root: str,
    data_env_setup: str | None,
    data_python: str,
) -> list[str]:
    runtime = _runtime(data_python, data_env_setup)
    script = Path(trajectory_root).expanduser() / "0_1th_box" / "gen_box.py"
    return python_data_command(
        runtime,
        script,
        ["--dataset_root", str(Path(save_path_temp).expanduser())],
    )


def inspect_annotation_outputs(
    *, save_path_temp: str, expected_clips: list[str] | None = None
) -> dict[str, Any]:
    temp_path = Path(save_path_temp).expanduser()
    samples_root = temp_path / "samples"
    expected = [str(item) for item in (expected_clips or [])]
    all_clip_dirs = _clip_dirs(samples_root)
    dirs_by_name: dict[str, list[Path]] = {}
    for clip_dir in all_clip_dirs:
        dirs_by_name.setdefault(clip_dir.name, []).append(clip_dir)

    clip_names = expected or sorted(dirs_by_name)
    clips: dict[str, dict[str, Any]] = {}
    missing_yaml_clips: list[str] = []
    yaml_paths: list[str] = []

    for clip_name in clip_names:
        clip_yaml: list[Path] = []
        clip_dir_paths = dirs_by_name.get(clip_name, [])
        for clip_dir in clip_dir_paths:
            clip_yaml.extend(_yaml_files(clip_dir))
        yaml_text = [str(path) for path in sorted(clip_yaml)]
        yaml_paths.extend(yaml_text)
        clips[clip_name] = {
            "clip_name": clip_name,
            "clip_dirs": [str(path) for path in clip_dir_paths],
            "yaml_count": len(yaml_text),
            "yaml_paths": yaml_text,
        }
        if not yaml_text:
            missing_yaml_clips.append(clip_name)

    ok = not missing_yaml_clips and (bool(clips) or bool(yaml_paths))
    result = {
        "ok": ok,
        "save_path_temp": str(temp_path),
        "samples_root": str(samples_root),
        "expected_clips": expected,
        "clips": clips,
        "yaml_paths": sorted(yaml_paths),
        "missing_yaml_clips": missing_yaml_clips,
    }
    if not ok:
        result["error_type"] = "missing_annotation_yaml"
        result["checkpoint_message"] = (
            "Manual annotation did not produce YAML for one or more expected clips. "
            "Retry annotation, skip the missing clips, or stop the run."
        )
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


def run_manual_box_annotation(
    *,
    save_path_temp: str,
    trajectory_root: str,
    data_env_setup: str | None,
    data_python: str,
    expected_clips: list[str] | None = None,
    timeout: int | None = None,
    dry_run: bool = True,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    temp_path = Path(save_path_temp).expanduser()
    trajectory_path = Path(trajectory_root).expanduser()
    command = build_annotation_command(
        save_path_temp=str(temp_path),
        trajectory_root=str(trajectory_path),
        data_env_setup=data_env_setup,
        data_python=data_python,
    )
    cwd = trajectory_path / "0_1th_box"
    logger = _logger(log_dir)
    base = {
        "save_path_temp": str(temp_path),
        "trajectory_root": str(trajectory_path),
        "data_env_setup": data_env_setup,
        "data_python": data_python,
        "expected_clips": [str(item) for item in (expected_clips or [])],
        "timeout": timeout,
        "dry_run": bool(dry_run),
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
        "cwd": str(cwd),
        "command": command,
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting manual annotation checkpoint",
            data=base,
        )

    inspection = inspect_annotation_outputs(
        save_path_temp=str(temp_path), expected_clips=expected_clips or []
    )
    if dry_run:
        return _finish(
            logger,
            {**base, **inspection, "ok": True, "planned_command": command},
            "planned manual annotation checkpoint",
        )

    script = trajectory_path / "0_1th_box" / "gen_box.py"
    if not cwd.is_dir() or not script.is_file():
        return _finish(
            logger,
            {
                **base,
                "ok": False,
                "error_type": "missing_annotation_script",
                "missing": [
                    {"type": "cwd", "path": str(cwd)},
                    {"type": "script", "path": str(script)},
                ],
            },
            "manual annotation script path is missing",
        )

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
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        if logger:
            logger.command(
                stage=_STAGE,
                command=command,
                cwd=str(cwd),
                return_code=None,
                stdout=stdout,
                stderr=stderr,
            )
        return _finish(
            logger,
            {
                **base,
                "ok": False,
                "error_type": "annotation_timeout",
                "stdout": stdout,
                "stderr": stderr,
            },
            "manual annotation command timed out",
        )

    if logger:
        logger.command(
            stage=_STAGE,
            command=command,
            cwd=str(cwd),
            return_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
    inspection = inspect_annotation_outputs(
        save_path_temp=str(temp_path), expected_clips=expected_clips or []
    )
    result = {
        **base,
        **inspection,
        "process_return_code": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }
    result["ok"] = proc.returncode == 0 and inspection["ok"]
    if proc.returncode != 0:
        result["error_type"] = "annotation_command_failed"
    return _finish(
        logger,
        result,
        (
            "manual annotation checkpoint completed"
            if result["ok"]
            else "manual annotation checkpoint failed"
        ),
    )

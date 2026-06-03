from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from data_juicer_agents.tools.vla._shared.config import VLARuntime
from data_juicer_agents.tools.vla._shared.logging import VLARunLogger
from data_juicer_agents.tools.vla._shared.runtime import data_runtime_command

_STAGE = "check_runtime"


def _agent_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _logger(log_dir: str | None) -> VLARunLogger | None:
    if not log_dir:
        return None
    return VLARunLogger.open(log_dir)


def _parse_version(text: str) -> str | None:
    match = re.search(r"(\d+\.\d+)(?:\.\d+)?", text)
    if match:
        return match.group(1)
    return None


def _base_payload(
    *,
    runtime: VLARuntime,
    data_python: str,
    expected_data_python_major_minor: str,
    dry_run: bool,
    run_id: str | None,
    log_dir: str | None,
) -> dict[str, Any]:
    agent_python_ok = sys.version_info >= (3, 10)
    setup_exists = (
        runtime.data_env_setup.exists() if runtime.data_env_setup is not None else None
    )
    warnings: list[str] = []
    if data_python == "python3":
        warnings.append(
            "data_python is 'python3'; use an absolute Python 3.8 executable "
            "on the server to avoid resolving to the Agent runtime"
        )

    return {
        "agent_python": sys.executable,
        "agent_python_version": _agent_version(),
        "agent_python_ok": agent_python_ok,
        "data_env_setup": (
            str(runtime.data_env_setup) if runtime.data_env_setup else None
        ),
        "data_env_setup_exists": setup_exists,
        "data_python": data_python,
        "expected_data_python_major_minor": expected_data_python_major_minor,
        "runtime_boundary": "agent_python_to_subprocess_data_python",
        "mode": "dry_run" if dry_run else "execute",
        "run_id": run_id,
        "log_dir": str(Path(log_dir).expanduser()) if log_dir else None,
        "warnings": warnings,
    }


def check_runtime(
    *,
    data_env_setup: str | None,
    data_python: str,
    expected_data_python_major_minor: str = "3.8",
    dry_run: bool = False,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    runtime = VLARuntime(
        data_python=data_python,
        data_env_setup=Path(data_env_setup).expanduser() if data_env_setup else None,
    )
    logger = _logger(log_dir)
    base = _base_payload(
        runtime=runtime,
        data_python=data_python,
        expected_data_python_major_minor=expected_data_python_major_minor,
        dry_run=dry_run,
        run_id=run_id,
        log_dir=log_dir,
    )
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_start",
            ok=True,
            message="starting VLA runtime precheck",
            data=base,
        )

    command = data_runtime_command(
        runtime,
        [
            data_python,
            "-c",
            (
                "import sys; "
                "print(f'{sys.version_info.major}."
                "{sys.version_info.minor}.{sys.version_info.micro}'); "
                "print(sys.executable)"
            ),
        ],
    )

    if dry_run:
        result = {
            "ok": True,
            "message": "VLA runtime precheck dry run",
            "command": command,
            **base,
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=True,
                message=result["message"],
                data=result,
            )
        return result

    if not base["agent_python_ok"]:
        result = {
            "ok": False,
            "message": "Agent runtime must use Python 3.10 or newer",
            "command": command,
            **base,
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message=result["message"],
                data=result,
            )
        return result

    if runtime.data_env_setup is not None and not base["data_env_setup_exists"]:
        result = {
            "ok": False,
            "message": "data runtime setup script is missing",
            "command": command,
            **base,
        }
        if logger:
            logger.event(
                stage=_STAGE,
                event_type="stage_end",
                ok=False,
                message=result["message"],
                data=result,
            )
        return result

    started = time.monotonic()
    proc = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed = time.monotonic() - started
    if logger:
        logger.command(
            stage=_STAGE,
            command=command,
            cwd=str(Path.cwd()),
            return_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    output_lines = (proc.stdout or proc.stderr).strip().splitlines()
    version_text = output_lines[0] if output_lines else ""
    data_python_version = _parse_version(version_text)
    data_python_executable = output_lines[1] if len(output_lines) > 1 else ""
    warnings = list(base["warnings"])
    if data_python_executable and Path(data_python_executable) == Path(sys.executable):
        warnings.append("data runtime Python resolves to the Agent Python executable")

    ok = (
        proc.returncode == 0
        and data_python_version == expected_data_python_major_minor
        and bool(base["agent_python_ok"])
    )
    result = {
        "ok": ok,
        "command": command,
        "return_code": proc.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "data_python_version_text": version_text,
        "data_python_version": data_python_version,
        "data_python_executable": data_python_executable,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "warnings": warnings,
        "message": "data runtime verified" if ok else "data runtime version mismatch",
        **{key: value for key, value in base.items() if key != "warnings"},
    }
    if logger:
        logger.event(
            stage=_STAGE,
            event_type="stage_end",
            ok=ok,
            message=result["message"],
            data=result,
        )
    return result

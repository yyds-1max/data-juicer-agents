from __future__ import annotations

import shlex
from pathlib import Path
from typing import Iterable, Sequence

from .config import VLAPaths, VLARuntime


def quote_argv(argv: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in argv)


def data_runtime_command(runtime: VLARuntime, argv: Sequence[str]) -> list[str]:
    command_argv = [str(part) for part in argv]
    if runtime.data_env_setup is None:
        return command_argv

    setup = shlex.quote(str(runtime.data_env_setup))
    return ["bash", "-lc", f"source {setup} && exec {quote_argv(command_argv)}"]


def python_data_command(
    runtime: VLARuntime, script_path: str | Path, args: Sequence[str]
) -> list[str]:
    script_args = [str(script_path), *[str(arg) for arg in args]]
    if runtime.data_env_setup is None:
        return [str(runtime.data_python), *script_args]

    setup = shlex.quote(str(runtime.data_env_setup))
    data_python = shlex.quote(str(runtime.data_python))
    shell = (
        f"export AGENT_DATA_PYTHON={data_python} && "
        f"source {setup} && "
        f'exec "$AGENT_DATA_PYTHON" {quote_argv(script_args)}'
    )
    return ["bash", "-lc", shell]


def run_u_python_command(
    runtime: VLARuntime, paths: VLAPaths, script_name: str, args: Sequence[str]
) -> list[str]:
    command_argv = [script_name, *[str(arg) for arg in args]]
    setup_lines: list[str] = []
    if runtime.data_env_setup is not None:
        setup_lines.extend(
            [
                f"export AGENT_DATA_PYTHON={shlex.quote(str(runtime.data_python))}",
                f"source {shlex.quote(str(runtime.data_env_setup))}",
            ]
        )
        exec_line = f'exec "$AGENT_DATA_PYTHON" {quote_argv(command_argv)}'
    else:
        exec_line = quote_argv([str(runtime.data_python), *command_argv])

    lines = [
        *setup_lines,
        "export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:${LD_LIBRARY_PATH:-}",
        "export LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}:"
        f"{shlex.quote(str(paths.shm_msgs_lib_dir))}",
        f"source {shlex.quote(str(paths.ros2_setup_bash))}",
        f"source {shlex.quote(str(paths.ros2_ws_setup_bash))}",
        exec_line,
    ]
    return ["bash", "-lc", " && ".join(lines)]

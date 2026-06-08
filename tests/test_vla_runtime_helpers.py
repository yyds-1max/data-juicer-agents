import json
import sys
from pathlib import Path

from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.tools.vla._shared.config import VLAPaths, VLARuntime
from data_juicer_agents.tools.vla._shared.runtime import (
    data_runtime_command,
    python_data_command,
    run_u_python_command,
)
from data_juicer_agents.tools.vla.check_runtime.logic import check_runtime
from data_juicer_agents.tools.vla.check_runtime.tool import VLA_CHECK_RUNTIME


def test_python_data_command_without_setup_uses_data_python():
    runtime = VLARuntime(data_python="/opt/py38/bin/python", data_env_setup=None)

    command = python_data_command(runtime, "/tmp/script.py", ["--name", "a b"])

    assert command == ["/opt/py38/bin/python", "/tmp/script.py", "--name", "a b"]


def test_python_data_command_with_setup_defers_python_resolution_until_after_source():
    runtime = VLARuntime(
        data_python="python3",
        data_env_setup=Path("/srv/setup data runtime.sh"),
    )

    command = python_data_command(runtime, "/tmp/script.py", ["--flag", "value"])

    assert command[:2] == ["bash", "-lc"]
    assert "export AGENT_DATA_PYTHON=python3" in command[2]
    assert "source '/srv/setup data runtime.sh'" in command[2]
    assert command[2].index("source '/srv/setup data runtime.sh'") < command[2].index(
        'exec "$AGENT_DATA_PYTHON"'
    )
    assert 'exec "$AGENT_DATA_PYTHON" /tmp/script.py --flag value' in command[2]


def test_data_runtime_command_wraps_binary_with_setup():
    runtime = VLARuntime(
        data_python="/usr/bin/python3.8",
        data_env_setup=Path("/srv/setup.sh"),
    )

    command = data_runtime_command(runtime, ["./bin/main", "--name", "a b"])

    assert command[:2] == ["bash", "-lc"]
    assert "source /srv/setup.sh" in command[2]
    assert "exec ./bin/main --name 'a b'" in command[2]


def test_run_u_python_command_sources_ros_and_library_paths():
    runtime = VLARuntime(
        data_python="/usr/bin/python3.8", data_env_setup=Path("/srv/setup.sh")
    )
    paths = VLAPaths(
        raw_root=Path("/raw"),
        clip_root=Path("/clip"),
        finish_root=Path("/finish"),
        data_toolbox_src=Path("/toolbox"),
        trajectory_root=Path("/traj"),
        gt_dog_root=Path("/gt"),
    )

    command = run_u_python_command(
        runtime, paths, "extract.py", ["--data_path", "/raw/date"]
    )

    assert command[:2] == ["bash", "-lc"]
    assert "source /srv/setup.sh" in command[2]
    assert "source /gt/modules/message/ros2/install/setup.bash" in command[2]
    assert "source /gt/modules/ros2_ws/src/install/setup.bash" in command[2]
    assert "shm/install/shm_msgs/lib" in command[2]
    assert 'exec "$AGENT_DATA_PYTHON" extract.py --data_path /raw/date' in command[2]


def test_check_runtime_dry_run_reports_wrapper_without_executing():
    result = check_runtime(
        data_env_setup="/srv/setup.sh",
        data_python="/usr/bin/python3.8",
        expected_data_python_major_minor="3.8",
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["data_python"] == "/usr/bin/python3.8"
    assert result["expected_data_python_major_minor"] == "3.8"
    assert result["mode"] == "dry_run"
    assert result["runtime_boundary"] == "agent_python_to_subprocess_data_python"


def test_check_runtime_writes_stage_events_when_log_dir_is_provided(tmp_path):
    log_dir = tmp_path / "run_logs"

    result = check_runtime(
        data_env_setup=None,
        data_python=sys.executable,
        expected_data_python_major_minor=(
            f"{sys.version_info.major}.{sys.version_info.minor}"
        ),
        dry_run=True,
        run_id="run_test",
        log_dir=str(log_dir),
    )

    events = (log_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()

    assert result["ok"] is True
    assert result["run_id"] == "run_test"
    assert result["log_dir"] == str(log_dir)
    assert [json.loads(line)["event_type"] for line in events] == [
        "stage_start",
        "stage_end",
    ]


def test_check_runtime_tool_creates_default_run_log_dir(tmp_path):
    result = VLA_CHECK_RUNTIME.execute(
        ToolContext(working_dir=str(tmp_path)),
        {
            "data_env_setup": None,
            "data_python": sys.executable,
            "expected_data_python_major_minor": (
                f"{sys.version_info.major}.{sys.version_info.minor}"
            ),
            "dry_run": True,
            "run_id": "run_auto",
        },
    )

    log_dir = tmp_path / "vla_runs" / "runtime" / "run_auto"

    assert result.ok is True
    assert result.data["run_id"] == "run_auto"
    assert result.data["log_dir"] == str(log_dir)
    assert (log_dir / "events.jsonl").exists()


def test_check_runtime_tool_defaults_to_data_runtime_environment(
    tmp_path, monkeypatch
):
    setup = tmp_path / "setup_data_runtime.sh"
    setup.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    monkeypatch.setenv("AGENT_DATA_ENV_SETUP", str(setup))
    monkeypatch.setenv("AGENT_DATA_PYTHON", "/usr/bin/python3.8")

    result = VLA_CHECK_RUNTIME.execute(
        ToolContext(working_dir=str(tmp_path)),
        {
            "dry_run": True,
            "run_id": "run_env_defaults",
        },
    )

    assert result.ok is True
    assert result.data["data_env_setup"] == str(setup)
    assert result.data["data_env_setup_exists"] is True
    assert result.data["data_python"] == "/usr/bin/python3.8"

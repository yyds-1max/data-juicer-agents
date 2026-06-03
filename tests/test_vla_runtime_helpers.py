from pathlib import Path

from data_juicer_agents.tools.vla._shared.config import VLAPaths, VLARuntime
from data_juicer_agents.tools.vla._shared.runtime import (
    data_runtime_command,
    python_data_command,
    run_u_python_command,
)


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
    assert command[2].index("source '/srv/setup data runtime.sh'") < command[
        2
    ].index('exec "$AGENT_DATA_PYTHON"')
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

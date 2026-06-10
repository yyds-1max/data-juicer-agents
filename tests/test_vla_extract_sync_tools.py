import json

from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.tools.vla.extract_and_sync.input import ExtractAndSyncInput
from data_juicer_agents.tools.vla.extract_and_sync.logic import (
    build_extract_sync_plan,
    extract_and_sync,
)
from data_juicer_agents.tools.vla.extract_and_sync.tool import VLA_EXTRACT_AND_SYNC


def test_build_extract_sync_plan_generates_one_extract_and_sync_command_per_segment(
    tmp_path,
):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    (raw_root / "20270515_temp" / "seg_a").mkdir(parents=True)
    toolbox.mkdir()

    result = build_extract_sync_plan(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup="/srv/setup.sh",
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
    )

    assert result["ok"] is True
    assert len(result["segments"]) == 1
    commands = result["segments"][0]["commands"]
    assert "1_extract_data_from_bag_multi_process_ros2_U_legacy.py" in " ".join(commands[0])
    assert "--data_path" in commands[0][-1]
    assert "2_sync_data_multi_process_U_legacy.py" in " ".join(commands[1])
    assert "seg_a_zhigu_wuhan" in commands[1][-1]


def test_build_extract_sync_plan_current_variant_uses_current_scripts(tmp_path):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    (raw_root / "20270605_temp" / "seg_a").mkdir(parents=True)
    toolbox.mkdir()

    result = build_extract_sync_plan(
        date="20270605",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup="/srv/setup.sh",
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="rs32_lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
        script_variant="go2w_current_topics",
    )

    joined = "\n".join(" ".join(cmd) for cmd in result["segments"][0]["commands"])
    assert result["script_variant"] == "go2w_current_topics"
    assert result["extract_script"] == "1_extract_data_from_bag_multi_process_ros2_U.py"
    assert result["sync_script"] == "2_sync_data_multi_process_U.py"
    assert "1_extract_data_from_bag_multi_process_ros2_U.py" in joined
    assert "2_sync_data_multi_process_U.py" in joined
    assert "_legacy.py" not in joined


def test_extract_and_sync_dry_run_does_not_create_clip_segment(tmp_path):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    (raw_root / "20270515_temp" / "seg_a").mkdir(parents=True)
    toolbox.mkdir()

    result = extract_and_sync(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert not (clip_root / "20270515" / "seg_a").exists()


def test_extract_and_sync_execute_creates_save_path_and_runs_commands(
    tmp_path, monkeypatch
):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    (raw_root / "20270515_temp" / "seg_a").mkdir(parents=True)
    toolbox.mkdir()
    calls = []

    def fake_run(command, cwd, text, stdout, stderr, check, env):
        calls.append(
            {
                "command": command,
                "cwd": cwd,
                "text": text,
                "stdout": stdout,
                "stderr": stderr,
                "check": check,
                "env": env,
            }
        )

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.extract_and_sync.logic.subprocess.run",
        fake_run,
    )

    result = extract_and_sync(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["completed_segments"] == ["seg_a"]
    assert (clip_root / "20270515" / "seg_a").is_dir()
    assert len(calls) == 2
    assert all(call["cwd"] == str(toolbox) for call in calls)
    assert all(call["check"] is False for call in calls)


def test_extract_and_sync_tool_dry_run_creates_default_log_dir(tmp_path):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    (raw_root / "20270515_temp" / "seg_a").mkdir(parents=True)
    toolbox.mkdir()

    result = VLA_EXTRACT_AND_SYNC.execute(
        ToolContext(working_dir=str(tmp_path)),
        {
            "date": "20270515",
            "selected_segments": ["seg_a"],
            "raw_root": str(raw_root),
            "clip_root": str(clip_root),
            "data_toolbox_src": str(toolbox),
            "data_env_setup": None,
            "data_python": "/usr/bin/python3.8",
            "processes_num": 4,
            "dry_run": True,
            "run_id": "run_extract_sync",
        },
    )

    log_dir = tmp_path / "vla_runs" / "20270515" / "run_extract_sync"

    assert result.ok is True
    assert result.data["dry_run"] is True
    assert result.data["run_id"] == "run_extract_sync"
    assert result.data["log_dir"] == str(log_dir)
    assert result.data["segments"][0]["name"] == "seg_a"
    events = (log_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["event_type"] for line in events] == [
        "stage_start",
        "stage_end",
    ]
    assert VLA_EXTRACT_AND_SYNC.name == "vla_extract_and_sync"
    assert VLA_EXTRACT_AND_SYNC.tags == ("vla", "execute")
    assert VLA_EXTRACT_AND_SYNC.effects == "execute"
    assert VLA_EXTRACT_AND_SYNC.confirmation == "required"


def test_extract_and_sync_input_accepts_logging_and_runtime_overrides():
    parsed = ExtractAndSyncInput.model_validate(
        {
            "date": "20270515",
            "selected_segments": ["seg_a"],
            "data_toolbox_src": "/toolbox",
            "run_id": "run_a",
            "log_dir": "/logs/run_a",
            "gt_dog_root": "/gt_dog_override",
            "extra_env": {"CUDA_VISIBLE_DEVICES": "0"},
        }
    )

    assert parsed.query_dir == "lidar_points"
    assert parsed.sync_output_dir == "sync_data"
    assert parsed.sequence_suffix == "zhigu_wuhan"
    assert parsed.dry_run is False
    assert parsed.run_id == "run_a"
    assert parsed.log_dir == "/logs/run_a"
    assert parsed.gt_dog_root == "/gt_dog_override"
    assert parsed.extra_env == {"CUDA_VISIBLE_DEVICES": "0"}


def test_extract_and_sync_dry_run_reports_missing_raw_segments_without_creating_clip(
    tmp_path,
):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    toolbox.mkdir()

    result = extract_and_sync(
        date="20270515",
        selected_segments=["seg_missing"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["error_type"] == "missing_raw_segments"
    assert result["missing_raw_segments"] == ["seg_missing"]
    assert not (clip_root / "20270515").exists()


def test_extract_and_sync_reports_missing_data_toolbox_src(tmp_path):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "missing_toolbox"
    (raw_root / "20270515_temp" / "seg_a").mkdir(parents=True)

    result = extract_and_sync(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["error_type"] == "missing_data_toolbox_src"
    assert result["data_toolbox_src"] == str(toolbox)
    assert not (clip_root / "20270515").exists()


def test_extract_and_sync_reports_no_selected_segments(tmp_path):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    toolbox.mkdir()

    result = extract_and_sync(
        date="20270515",
        selected_segments=[" "],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["error_type"] == "no_selected_segments"
    assert not (clip_root / "20270515").exists()


def test_extract_and_sync_execute_merges_extra_env_into_subprocess_env(
    tmp_path, monkeypatch
):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    (raw_root / "20270515_temp" / "seg_a").mkdir(parents=True)
    toolbox.mkdir()
    calls = []

    def fake_run(command, cwd, text, stdout, stderr, check, env):
        calls.append({"command": command, "env": env})

        class Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.extract_and_sync.logic.subprocess.run",
        fake_run,
    )

    result = extract_and_sync(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
        gt_dog_root="/custom/gt",
        extra_env={"CUDA_VISIBLE_DEVICES": "0", "VLA_MODE": "test"},
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["gt_dog_root"] == "/custom/gt"
    assert result["extra_env"] == {"CUDA_VISIBLE_DEVICES": "0", "VLA_MODE": "test"}
    assert all(call["env"]["CUDA_VISIBLE_DEVICES"] == "0" for call in calls)
    assert all(call["env"]["VLA_MODE"] == "test" for call in calls)
    assert all(
        "/custom/gt/modules/message/ros2/install/setup.bash" in call["command"][2]
        for call in calls
    )


def test_extract_and_sync_logger_records_each_command(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw"
    clip_root = tmp_path / "clip"
    toolbox = tmp_path / "toolbox"
    log_dir = tmp_path / "logs"
    (raw_root / "20270515_temp" / "seg_a").mkdir(parents=True)
    toolbox.mkdir()

    def fake_run(command, cwd, text, stdout, stderr, check, env):
        class Result:
            returncode = 0
            stdout = "command stdout"
            stderr = "command stderr"

        return Result()

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.extract_and_sync.logic.subprocess.run",
        fake_run,
    )

    result = extract_and_sync(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        data_toolbox_src=str(toolbox),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        processes_num=4,
        query_dir="lidar_points",
        sync_output_dir="sync_data",
        sequence_suffix="zhigu_wuhan",
        dry_run=False,
        run_id="run_direct",
        log_dir=str(log_dir),
    )

    assert result["ok"] is True
    command_log = (log_dir / "commands.log").read_text(encoding="utf-8")
    assert command_log.count("return_code=0") == 2
    assert "1_extract_data_from_bag_multi_process_ros2_U_legacy.py" in command_log
    assert "2_sync_data_multi_process_U_legacy.py" in command_log
    assert "command stdout" in (log_dir / "stdout.log").read_text(encoding="utf-8")
    assert "command stderr" in (log_dir / "stderr.log").read_text(encoding="utf-8")

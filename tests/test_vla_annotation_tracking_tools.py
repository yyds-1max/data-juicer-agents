import json
import subprocess

from data_juicer_agents.tools.vla.run_manual_box_annotation.logic import (
    build_annotation_command,
    inspect_annotation_outputs,
)
from data_juicer_agents.tools.vla.run_manual_box_annotation.tool import (
    VLA_RUN_MANUAL_BOX_ANNOTATION,
)
from data_juicer_agents.tools.vla.run_tracking.input import RunTrackingInput
from data_juicer_agents.tools.vla.run_tracking.logic import (
    build_tracking_plan,
    run_tracking,
)
from data_juicer_agents.tools.vla.run_tracking.tool import VLA_RUN_TRACKING


def test_inspect_annotation_outputs_finds_yaml_per_clip(tmp_path):
    clip = tmp_path / "finish_temp" / "samples" / "20270515" / "clip_a"
    clip.mkdir(parents=True)
    (clip / "master_black_black_black.yaml").write_text(
        "box: [[1, 2, 3, 4]]\n", encoding="utf-8"
    )

    result = inspect_annotation_outputs(
        save_path_temp=str(tmp_path / "finish_temp"), expected_clips=["clip_a"]
    )

    assert result["ok"] is True
    assert result["clips"]["clip_a"]["yaml_count"] == 1


def test_inspect_annotation_outputs_reports_missing_yaml():
    result = inspect_annotation_outputs(
        save_path_temp="/missing/path", expected_clips=["clip_a"]
    )

    assert result["ok"] is False
    assert result["missing_yaml_clips"] == ["clip_a"]


def test_build_annotation_command_uses_data_python():
    command = build_annotation_command(
        save_path_temp="/finish/temp",
        trajectory_root="/traj",
        data_env_setup="/srv/setup.sh",
        data_python="/usr/bin/python3.8",
    )

    assert command[:2] == ["bash", "-lc"]
    assert "gen_box.py" in command[2]
    assert "--dataset_root /finish/temp" in command[2]


def test_build_tracking_plan_runs_one_binary_per_yaml(tmp_path):
    clip = tmp_path / "finish_temp" / "samples" / "20270515" / "clip_a"
    clip.mkdir(parents=True)
    (clip / "master_black_black_black.yaml").write_text(
        "box: [[1, 2, 3, 4]]\n", encoding="utf-8"
    )

    result = build_tracking_plan(
        save_path_temp=str(tmp_path / "finish_temp"),
        trajectory_root="/traj",
        data_env_setup="/srv/setup.sh",
    )

    assert result["ok"] is True
    assert len(result["tracking_jobs"]) == 1
    assert result["tracking_jobs"][0]["command"][:2] == ["bash", "-lc"]
    assert "exec ./bin/main" in result["tracking_jobs"][0]["command"][2]


def test_annotation_and_tracking_tools_require_confirmation():
    assert VLA_RUN_MANUAL_BOX_ANNOTATION.name == "vla_run_manual_box_annotation"
    assert VLA_RUN_MANUAL_BOX_ANNOTATION.effects == "execute"
    assert VLA_RUN_MANUAL_BOX_ANNOTATION.confirmation == "required"
    assert VLA_RUN_TRACKING.name == "vla_run_tracking"
    assert VLA_RUN_TRACKING.effects == "execute"
    assert VLA_RUN_TRACKING.confirmation == "required"


def test_run_tracking_timeout_returns_structured_failure_and_stage_end(
    tmp_path, monkeypatch
):
    save_path_temp = tmp_path / "finish_temp"
    clip = save_path_temp / "samples" / "20270515" / "clip_a"
    clip.mkdir(parents=True)
    first_yaml = clip / "master_black_black_black.yaml"
    second_yaml = clip / "other_red_blue.yaml"
    first_yaml.write_text("box: [[1, 2, 3, 4]]\n", encoding="utf-8")
    second_yaml.write_text("box: [[5, 6, 7, 8]]\n", encoding="utf-8")
    trajectory_root = tmp_path / "traj"
    tracking_cwd = trajectory_root / "1_onnx_tam"
    (tracking_cwd / "bin").mkdir(parents=True)
    (tracking_cwd / "bin" / "main").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )
    output_root = trajectory_root / "Data" / "1_img_output"
    log_dir = tmp_path / "logs"
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        if len(calls) == 1:
            (output_root / "tracking_img").mkdir(parents=True)
            (output_root / "img_points.txt").write_text("points\n", encoding="utf-8")
            return subprocess.CompletedProcess(
                args=args[0], returncode=0, stdout="first ok\n", stderr=""
            )
        raise subprocess.TimeoutExpired(
            cmd=args[0], timeout=3, output="partial out\n", stderr="partial err\n"
        )

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.run_tracking.logic.subprocess.run", fake_run
    )

    result = run_tracking(
        save_path_temp=str(save_path_temp),
        trajectory_root=str(trajectory_root),
        data_env_setup=None,
        dry_run=False,
        timeout=3,
        log_dir=str(log_dir),
    )

    assert result["ok"] is False
    assert result["error_type"] == "tracking_timeout"
    assert result["failed_yaml_paths"] == [str(second_yaml)]
    assert len(result["completed_jobs"]) == 1
    assert result["completed_jobs"][0]["yaml_path"] == str(first_yaml)
    assert len(result["command_results"]) == 2
    assert result["command_results"][1]["timed_out"] is True
    assert result["command_results"][1]["stdout"] == "partial out\n"
    assert result["command_results"][1]["stderr"] == "partial err\n"
    events = [
        json.loads(line)["event_type"]
        for line in (log_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events == ["stage_start", "stage_end"]
    assert "partial out\n" in (log_dir / "stdout.log").read_text(encoding="utf-8")
    assert "partial err\n" in (log_dir / "stderr.log").read_text(encoding="utf-8")


def test_run_tracking_input_accepts_cuda_env():
    args = RunTrackingInput.model_validate(
        {
            "save_path_temp": "/finish/temp",
            "cuda_env": {"CUDA_VISIBLE_DEVICES": "0"},
        }
    )

    assert args.cuda_env == {"CUDA_VISIBLE_DEVICES": "0"}


def test_run_tracking_merges_cuda_env_into_subprocess_env(tmp_path, monkeypatch):
    save_path_temp = tmp_path / "finish_temp"
    clip = save_path_temp / "samples" / "20270515" / "clip_a"
    clip.mkdir(parents=True)
    (clip / "master_black_black_black.yaml").write_text(
        "box: [[1, 2, 3, 4]]\n", encoding="utf-8"
    )
    trajectory_root = tmp_path / "traj"
    tracking_cwd = trajectory_root / "1_onnx_tam"
    (tracking_cwd / "bin").mkdir(parents=True)
    (tracking_cwd / "bin" / "main").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )
    output_root = trajectory_root / "Data" / "1_img_output"
    captured_env = {}

    def fake_run(*args, **kwargs):
        captured_env.update(kwargs["env"])
        (output_root / "tracking_img").mkdir(parents=True)
        (output_root / "img_points.txt").write_text("points\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="ok\n", stderr=""
        )

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.run_tracking.logic.subprocess.run", fake_run
    )

    result = run_tracking(
        save_path_temp=str(save_path_temp),
        trajectory_root=str(trajectory_root),
        data_env_setup=None,
        cuda_env={"CUDA_VISIBLE_DEVICES": "0"},
        extra_env={"TRACKING_MODE": "server"},
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["cuda_env"] == {"CUDA_VISIBLE_DEVICES": "0"}
    assert captured_env["CUDA_VISIBLE_DEVICES"] == "0"
    assert captured_env["TRACKING_MODE"] == "server"

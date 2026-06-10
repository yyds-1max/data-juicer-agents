import json
import subprocess

from data_juicer_agents.tools.vla.run_projection_and_trajectory.logic import (
    build_projection_trajectory_plan,
    run_projection_and_trajectory,
)
from data_juicer_agents.tools.vla.run_projection_and_trajectory.tool import (
    VLA_RUN_PROJECTION_AND_TRAJECTORY,
)
from data_juicer_agents.tools.vla.validate_outputs.logic import validate_outputs
from data_juicer_agents.tools.vla.validate_outputs.tool import VLA_VALIDATE_OUTPUTS


def test_build_projection_trajectory_plan_defaults_to_required_gridmap_move():
    result = build_projection_trajectory_plan(
        save_path="/finish/20270515",
        save_path_temp="/finish/20270515_temp",
        trajectory_root="/traj",
        data_env_setup="/srv/setup.sh",
        data_python="/usr/bin/python3.8",
    )

    names = [step["name"] for step in result["steps"]]
    assert "copy_gridmap" not in names
    joined = "\n".join(" ".join(item["command"]) for item in result["steps"])
    assert "NuscenesAanlysis_smart_pts_project/main.py" in joined
    assert "2_pt_project/0_img2world.py" in joined
    assert "2_pt_project/4_speed_direction_odom.py" in joined
    assert "2_pt_project/2_othermethod_cjl.py" in joined
    assert "2_pt_project/3_move_dir.py" in joined
    assert "2_pt_project/3_move_dir_no_gridmap.py" not in joined
    assert "cp_gridmap.py" not in joined


def test_build_projection_trajectory_plan_0525_with_gridmap_uses_0525_script():
    result = build_projection_trajectory_plan(
        save_path="/finish/20270605",
        save_path_temp="/finish/20270605_temp",
        trajectory_root="/traj",
        data_env_setup="/srv/setup.sh",
        data_python="/usr/bin/python3.8",
        trajectory_variant="cjl_0525_with_gridmap",
    )

    names = [step["name"] for step in result["steps"]]
    assert "copy_gridmap" not in names
    joined = "\n".join(" ".join(item["command"]) for item in result["steps"])
    assert "2_pt_project/2_othermethod_cjl_0525.py" in joined
    assert "2_pt_project/3_move_dir.py" in joined
    assert "2_pt_project/3_move_dir_no_gridmap.py" not in joined


def test_validate_outputs_full_reports_missing_and_present(tmp_path):
    clip_root = tmp_path / "clip"
    finish_root = tmp_path / "finish"
    (clip_root / "20270515" / "seg_a" / "sync_data").mkdir(parents=True)
    (finish_root / "20270515_temp" / "samples" / "20270515" / "clip_a").mkdir(
        parents=True
    )

    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )

    assert result["ok"] is False
    assert result["checks"]["clip_sync_data"]["ok"] is True
    assert result["checks"]["finish_temp_samples"]["ok"] is True
    assert result["checks"]["finish_final"]["ok"] is False
    assert result["suggested_next_action"] == "run_manual_box_annotation"


def test_validate_outputs_suggests_projection_when_only_final_is_missing(tmp_path):
    clip_root = tmp_path / "clip"
    finish_root = tmp_path / "finish"
    clip_dir = finish_root / "20270515_temp" / "samples" / "20270515" / "clip_a"
    (clip_root / "20270515" / "seg_a" / "sync_data").mkdir(parents=True)
    clip_dir.mkdir(parents=True)
    (clip_dir / "master_black_black.yaml").write_text("box: []\n", encoding="utf-8")
    (clip_dir / "img_master_black_black.txt").write_text("points\n", encoding="utf-8")

    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )

    assert result["ok"] is False
    assert result["checks"]["annotation_yaml"]["ok"] is True
    assert result["checks"]["tracking_outputs"]["ok"] is True
    assert result["checks"]["finish_final"]["ok"] is False
    assert result["suggested_next_action"] == "run_projection_and_trajectory"


def test_validate_outputs_full_passes_with_expected_outputs(tmp_path):
    clip_root = tmp_path / "clip"
    finish_root = tmp_path / "finish"
    clip_dir = finish_root / "20270515_temp" / "samples" / "20270515" / "clip_a"
    final_clip = finish_root / "20270515" / "seg_a" / "clip_a"
    (clip_root / "20270515" / "seg_a" / "sync_data").mkdir(parents=True)
    clip_dir.mkdir(parents=True)
    (clip_dir / "master_black_black.yaml").write_text("box: []\n", encoding="utf-8")
    (clip_dir / "img_master_black_black.txt").write_text("points\n", encoding="utf-8")
    (final_clip / "rout_plot_v2").mkdir(parents=True)
    (final_clip / "clip_a_trajectory.json").write_text("[]\n", encoding="utf-8")
    (final_clip / "clip_a_speed_direction.json").write_text("{}\n", encoding="utf-8")
    (final_clip / "master_black_black_world.txt").write_text("1 2 3\n", encoding="utf-8")
    (final_clip / "grid_map").mkdir()
    (final_clip / "grid_map" / "123.json").write_text("{}\n", encoding="utf-8")

    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )

    assert result["ok"] is True
    assert result["checks"]["annotation_yaml"]["count"] == 1
    assert result["checks"]["tracking_outputs"]["count"] == 1
    assert result["checks"]["final_outputs"]["ok"] is True
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["ok"] is True
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["grid_map"] == str(
        final_clip / "grid_map"
    )
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["path"] == str(
        final_clip
    )
    assert result["suggested_next_action"] == "pipeline_complete"


def test_validate_outputs_full_rejects_empty_final_dir(tmp_path):
    clip_root = tmp_path / "clip"
    finish_root = tmp_path / "finish"
    clip_dir = finish_root / "20270515_temp" / "samples" / "20270515" / "clip_a"
    (clip_root / "20270515" / "seg_a" / "sync_data").mkdir(parents=True)
    clip_dir.mkdir(parents=True)
    (clip_dir / "master_black_black.yaml").write_text("box: []\n", encoding="utf-8")
    (clip_dir / "img_master_black_black.txt").write_text("points\n", encoding="utf-8")
    (finish_root / "20270515").mkdir(parents=True)

    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )

    assert result["ok"] is False
    assert result["checks"]["finish_final"]["ok"] is True
    assert result["checks"]["final_outputs"]["ok"] is False
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["missing"] == [
        "final_clip_dir",
        "rout_plot_v2",
        "trajectory_json",
        "speed_direction_json",
        "world_result_txt",
        "grid_map",
    ]


def test_validate_outputs_reports_each_missing_final_clip_output(tmp_path):
    clip_root = tmp_path / "clip"
    finish_root = tmp_path / "finish"
    temp_clip = finish_root / "20270515_temp" / "samples" / "20270515" / "clip_a"
    final_clip = finish_root / "20270515" / "seg_a" / "clip_a"
    (clip_root / "20270515" / "seg_a" / "sync_data").mkdir(parents=True)
    temp_clip.mkdir(parents=True)
    (temp_clip / "master_black_black.yaml").write_text("box: []\n", encoding="utf-8")
    (temp_clip / "img_master_black_black.txt").write_text("points\n", encoding="utf-8")
    final_clip.mkdir(parents=True)

    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["missing"] == [
        "rout_plot_v2",
        "trajectory_json",
        "speed_direction_json",
        "world_result_txt",
        "grid_map",
    ]

    (final_clip / "rout_plot_v2").mkdir()
    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["missing"] == [
        "trajectory_json",
        "speed_direction_json",
        "world_result_txt",
        "grid_map",
    ]

    (final_clip / "clip_a_trajectory.json").write_text("[]\n", encoding="utf-8")
    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["missing"] == [
        "speed_direction_json",
        "world_result_txt",
        "grid_map",
    ]

    (final_clip / "clip_a_speed_direction.json").write_text("{}\n", encoding="utf-8")
    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["missing"] == [
        "world_result_txt",
        "grid_map",
    ]

    (final_clip / "img_master_black_black.txt").write_text("image points\n", encoding="utf-8")
    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["missing"] == [
        "world_result_txt",
        "grid_map",
    ]

    (final_clip / "other_red_world.txt").write_text("1 2 3\n", encoding="utf-8")
    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["missing"] == [
        "grid_map"
    ]
    assert result["ok"] is False

    (final_clip / "grid_map").mkdir()
    result = validate_outputs(
        date="20270515",
        clip_root=str(clip_root),
        finish_root=str(finish_root),
        selected_segments=["seg_a"],
        level="full",
    )
    assert result["checks"]["final_outputs"]["clips"]["clip_a"]["missing"] == []
    assert result["ok"] is True


def test_run_projection_and_trajectory_dry_run_returns_planned_outputs():
    result = run_projection_and_trajectory(
        save_path="/finish/20270515",
        save_path_temp="/finish/20270515_temp",
        trajectory_root="/traj",
        data_env_setup="/srv/setup.sh",
        data_python="/usr/bin/python3.8",
        dry_run=True,
    )

    planned = result["planned_outputs"]
    assert result["output_paths"] == planned
    assert "generated_projection_files" in planned
    assert "world_coordinate_files" in planned
    assert "speed_direction_outputs" in planned
    assert "trajectory_outputs" in planned
    assert "moved_final_result_paths" in planned
    assert "/finish/20270515_temp" in planned["generated_projection_files"][0]
    assert "/finish/20270515/*/*" in planned["moved_final_result_paths"][0]


def test_run_projection_and_trajectory_execute_returns_actual_output_paths(
    tmp_path, monkeypatch
):
    save_path = tmp_path / "finish" / "20270515"
    save_path_temp = tmp_path / "finish" / "20270515_temp"
    temp_clip = save_path_temp / "samples" / "20270515" / "clip_a"
    temp_clip.mkdir(parents=True)
    (temp_clip / "grid_map").mkdir()
    trajectory_root = tmp_path / "traj"
    for script in [
        trajectory_root / "NuscenesAanlysis_smart_pts_project" / "main.py",
        trajectory_root / "2_pt_project" / "0_img2world.py",
        trajectory_root / "2_pt_project" / "4_speed_direction_odom.py",
        trajectory_root / "2_pt_project" / "2_othermethod_cjl.py",
        trajectory_root / "2_pt_project" / "3_move_dir.py",
    ]:
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# legacy script placeholder\n", encoding="utf-8")

    def fake_run(*args, **kwargs):
        (temp_clip / "project_npy").mkdir(parents=True, exist_ok=True)
        (temp_clip / "project_npy" / "points.npy").write_text("npy\n", encoding="utf-8")
        (temp_clip / "master_black_world.txt").write_text("1 2 3\n", encoding="utf-8")
        (temp_clip / "clip_a_speed_direction.json").write_text("temp\n", encoding="utf-8")
        final_clip = save_path / "seg_a" / "clip_a"
        (final_clip / "rout_plot_v2").mkdir(parents=True, exist_ok=True)
        (final_clip / "grid_map").mkdir(parents=True, exist_ok=True)
        (final_clip / "grid_map" / "123.json").write_text("{}\n", encoding="utf-8")
        (final_clip / "clip_a_trajectory.json").write_text("[]\n", encoding="utf-8")
        (final_clip / "clip_a_speed_direction.json").write_text("{}\n", encoding="utf-8")
        (final_clip / "master_black_world.txt").write_text("1 2 3\n", encoding="utf-8")
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="ok\n", stderr=""
        )

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.run_projection_and_trajectory.logic.subprocess.run",
        fake_run,
    )

    result = run_projection_and_trajectory(
        save_path=str(save_path),
        save_path_temp=str(save_path_temp),
        trajectory_root=str(trajectory_root),
        data_env_setup=None,
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["generated_projection_files"] == [
        str(temp_clip / "project_npy" / "points.npy")
    ]
    assert result["world_coordinate_files"] == [
        str(temp_clip / "master_black_world.txt"),
        str(save_path / "seg_a" / "clip_a" / "master_black_world.txt"),
    ]
    assert result["speed_direction_outputs"] == [
        str(temp_clip / "clip_a_speed_direction.json"),
        str(save_path / "seg_a" / "clip_a" / "clip_a_speed_direction.json"),
    ]
    assert result["trajectory_outputs"] == [
        str(save_path / "seg_a" / "clip_a" / "clip_a_trajectory.json")
    ]
    assert str(save_path / "seg_a" / "clip_a") in result["moved_final_result_paths"]
    assert (
        str(save_path / "seg_a" / "clip_a" / "rout_plot_v2")
        in result["moved_final_result_paths"]
    )
    assert (
        str(save_path / "seg_a" / "clip_a" / "master_black_world.txt")
        in result["moved_final_result_paths"]
    )
    assert result["output_paths"]["moved_final_result_paths"] == result[
        "moved_final_result_paths"
    ]


def test_run_projection_and_trajectory_timeout_writes_stage_end(tmp_path, monkeypatch):
    save_path = tmp_path / "finish" / "20270515"
    save_path_temp = tmp_path / "finish" / "20270515_temp"
    (save_path_temp / "samples" / "20270515" / "clip_a").mkdir(parents=True)
    (save_path_temp / "samples" / "20270515" / "clip_a" / "grid_map").mkdir()
    trajectory_root = tmp_path / "traj"
    for script in [
        trajectory_root / "NuscenesAanlysis_smart_pts_project" / "main.py",
        trajectory_root / "2_pt_project" / "0_img2world.py",
        trajectory_root / "2_pt_project" / "4_speed_direction_odom.py",
        trajectory_root / "2_pt_project" / "2_othermethod_cjl.py",
        trajectory_root / "2_pt_project" / "3_move_dir.py",
    ]:
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text("# legacy script placeholder\n", encoding="utf-8")
    log_dir = tmp_path / "logs"

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=args[0], timeout=3, output="partial out\n", stderr="partial err\n"
        )

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.run_projection_and_trajectory.logic.subprocess.run",
        fake_run,
    )

    result = run_projection_and_trajectory(
        save_path=str(save_path),
        save_path_temp=str(save_path_temp),
        trajectory_root=str(trajectory_root),
        data_env_setup=None,
        dry_run=False,
        timeout=3,
        log_dir=str(log_dir),
    )

    assert result["ok"] is False
    assert result["error_type"] == "projection_trajectory_timeout"
    assert result["command_results"][0]["timed_out"] is True
    events = [
        json.loads(line)["event_type"]
        for line in (log_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert events == ["stage_start", "stage_end"]


def test_projection_and_validation_tool_specs_have_expected_effects():
    assert VLA_RUN_PROJECTION_AND_TRAJECTORY.name == "vla_run_projection_and_trajectory"
    assert VLA_RUN_PROJECTION_AND_TRAJECTORY.effects == "execute"
    assert VLA_RUN_PROJECTION_AND_TRAJECTORY.confirmation == "required"
    assert VLA_VALIDATE_OUTPUTS.name == "vla_validate_outputs"
    assert VLA_VALIDATE_OUTPUTS.effects == "read"
    assert VLA_VALIDATE_OUTPUTS.confirmation == "none"

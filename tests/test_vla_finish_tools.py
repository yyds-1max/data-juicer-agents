import json

from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.tools.vla.build_noobscenes_inputs.logic import (
    build_noobscenes_inputs,
    build_noobscenes_plan,
)
from data_juicer_agents.tools.vla.build_noobscenes_inputs.tool import (
    VLA_BUILD_NOOBSCENES_INPUTS,
)
from data_juicer_agents.tools.vla.list_clip_segments.logic import list_clip_segments
from data_juicer_agents.tools.vla.list_clip_segments.tool import VLA_LIST_CLIP_SEGMENTS
from data_juicer_agents.tools.vla.prepare_finish_dataset.logic import (
    prepare_finish_dataset,
)
from data_juicer_agents.tools.vla.prepare_finish_dataset.tool import (
    VLA_PREPARE_FINISH_DATASET,
)


def test_list_clip_segments_marks_sync_data(tmp_path):
    clip = tmp_path / "clip" / "20270515" / "seg_a" / "sync_data"
    clip.mkdir(parents=True)

    result = list_clip_segments(date="20270515", clip_root=str(tmp_path / "clip"))

    assert result["ok"] is True
    assert result["segments"][0]["name"] == "seg_a"
    assert result["segments"][0]["has_sync_data"] is True


def test_prepare_finish_dataset_dry_run_reports_copy_plan(tmp_path):
    src = (
        tmp_path
        / "clip"
        / "20270515"
        / "seg_a"
        / "sync_data"
        / "20260515_102948_zhigu_wuhan_0"
    )
    (src / "fisheye_front").mkdir(parents=True)
    (src / "r32_rslidar_points").mkdir()
    sensors = tmp_path / "traj" / "NoobScenes" / "params" / "20260409_U" / "sensors"
    sensors.mkdir(parents=True)

    result = prepare_finish_dataset(
        date="20270515",
        selected_segments=["seg_a"],
        scene_mode="out",
        clip_root=str(tmp_path / "clip"),
        finish_root=str(tmp_path / "finish"),
        trajectory_root=str(tmp_path / "traj"),
        sensor_params_dir=str(sensors),
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["save_path_temp"].endswith("finish/20270515_temp")
    assert result["clips"][0]["clip_name"] == "20260515_102948_zhigu_wuhan_0"


def test_prepare_finish_dataset_execute_copies_clip_and_sensors(tmp_path):
    src = (
        tmp_path
        / "clip"
        / "20270515"
        / "seg_a"
        / "sync_data"
        / "20260515_102948_zhigu_wuhan_0"
    )
    (src / "fisheye_front").mkdir(parents=True)
    (src / "fisheye_front" / "000001.jpg").write_text("image", encoding="utf-8")
    (src / "r32_rslidar_points").mkdir()
    (src / "r32_rslidar_points" / "000001.bin").write_text("points", encoding="utf-8")
    sensors = tmp_path / "traj" / "NoobScenes" / "params" / "20260409_U" / "sensors"
    sensors.mkdir(parents=True)
    (sensors / "front.json").write_text("{}", encoding="utf-8")

    result = prepare_finish_dataset(
        date="20270515",
        selected_segments=["seg_a"],
        scene_mode="out",
        clip_root=str(tmp_path / "clip"),
        finish_root=str(tmp_path / "finish"),
        trajectory_root=str(tmp_path / "traj"),
        sensor_params_dir=str(sensors),
        dry_run=False,
    )

    target = (
        tmp_path
        / "finish"
        / "20270515_temp"
        / "samples"
        / "20270515"
        / "20260515_102948_zhigu_wuhan_0"
    )
    assert result["ok"] is True
    assert (target / "fisheye_front" / "000001.jpg").is_file()
    assert (target / "r32_rslidar_points" / "000001.bin").is_file()
    assert (target / "sensors" / "front.json").is_file()


def test_prepare_finish_dataset_fails_when_required_subdirectory_is_missing(tmp_path):
    src = (
        tmp_path
        / "clip"
        / "20270515"
        / "seg_a"
        / "sync_data"
        / "20260515_102948_zhigu_wuhan_0"
    )
    (src / "fisheye_front").mkdir(parents=True)
    sensors = tmp_path / "traj" / "NoobScenes" / "params" / "20260409_U" / "sensors"
    sensors.mkdir(parents=True)

    result = prepare_finish_dataset(
        date="20270515",
        selected_segments=["seg_a"],
        scene_mode="out",
        clip_root=str(tmp_path / "clip"),
        finish_root=str(tmp_path / "finish"),
        trajectory_root=str(tmp_path / "traj"),
        sensor_params_dir=str(sensors),
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["error_type"] == "missing_required_subdirectories"
    assert result["missing_subdirectories"] == [
        {
            "clip_name": "20260515_102948_zhigu_wuhan_0",
            "subdir": "r32_rslidar_points",
            "path": str(src / "r32_rslidar_points"),
        }
    ]


def test_build_noobscenes_plan_uses_python_data_command(tmp_path):
    result = build_noobscenes_plan(
        save_path_temp=str(tmp_path / "finish_temp"),
        trajectory_root="/traj",
        data_env_setup="/srv/setup.sh",
        data_python="/usr/bin/python3.8",
        dataset_version="v1.0-develop",
    )

    assert result["ok"] is True
    assert len(result["commands"]) >= 5
    joined = "\n".join(" ".join(cmd) for cmd in result["commands"])
    assert "0_creat_box.py" in joined
    assert "1_odom_convert.py" in joined
    assert "2_resize.py" in joined
    assert "img2video.py" in joined


def test_build_noobscenes_dry_run_reports_outputs_and_missing_warnings(tmp_path):
    save_path_temp = tmp_path / "finish" / "20270515_temp"
    clip = save_path_temp / "samples" / "20270515" / "20260515_102948_zhigu_wuhan_0"
    (clip / "fisheye_front").mkdir(parents=True)

    result = build_noobscenes_inputs(
        save_path_temp=str(save_path_temp),
        trajectory_root=str(tmp_path / "traj"),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["generated_metadata_paths"]["trainval_dir"] == str(
        save_path_temp / "v1.0-trainval"
    )
    assert result["video_paths"] == [
        str(clip / "dog.mp4"),
    ]
    assert {
        "type": "missing_images",
        "clip_name": "20260515_102948_zhigu_wuhan_0",
        "path": str(clip / "fisheye_front"),
    } in result["warnings"]


def test_build_noobscenes_dry_run_warns_when_samples_are_missing(tmp_path):
    save_path_temp = tmp_path / "finish" / "20270515_temp"

    result = build_noobscenes_inputs(
        save_path_temp=str(save_path_temp),
        trajectory_root=str(tmp_path / "traj"),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["clips"] == []
    assert result["video_paths"] == []
    assert result["warnings"] == [
        {
            "type": "missing_samples_dir",
            "path": str(save_path_temp / "samples"),
        }
    ]


def _event_types(log_dir):
    lines = (log_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["event_type"] for line in lines]


def _create_required_legacy_noobscenes_paths(trajectory_root):
    noobscenes = trajectory_root / "NoobScenes"
    include = noobscenes / "include"
    video_root = trajectory_root / "0_1th_box"
    include.mkdir(parents=True, exist_ok=True)
    video_root.mkdir(parents=True, exist_ok=True)
    for script in ("0_creat_box.py", "1_odom_convert.py", "2_resize.py"):
        (include / script).write_text("print('ok')\n", encoding="utf-8")
    (noobscenes / "main_smart_odom.py").write_text("print('ok')\n", encoding="utf-8")
    (video_root / "img2video.py").write_text("print('ok')\n", encoding="utf-8")


def _configure_noobscenes_failure_case(tmp_path, case):
    save_path_temp = tmp_path / case / "finish_temp"
    trajectory_root = tmp_path / case / "traj"
    noobscenes = trajectory_root / "NoobScenes"
    _create_required_legacy_noobscenes_paths(trajectory_root)
    clip = save_path_temp / "samples" / "20270515" / "20260515_102948_zhigu_wuhan_0"
    (clip / "fisheye_front").mkdir(parents=True)
    (clip / "fisheye_front" / "000001.jpg").write_text("image", encoding="utf-8")
    (clip / "r32_rslidar_points").mkdir()
    if case == "workspace":
        (noobscenes / "samples").mkdir()
    if case == "copy_map":
        generated = noobscenes / "v1.0-develop"
        generated.mkdir()
        (generated / "sample.json").write_text("{}", encoding="utf-8")
    return save_path_temp, trajectory_root


def test_build_noobscenes_failure_paths_write_stage_end(monkeypatch, tmp_path):
    cases = {
        "workspace": ([0, 0, 0], "samples_path_exists_not_symlink", None),
        "metadata_command": (
            [0, 0, 0, 1],
            "noobscenes_command_failed",
            "build_noobscenes_metadata",
        ),
        "move_dataset": ([0, 0, 0, 0], "missing_dataset_version", None),
        "copy_map": ([0, 0, 0, 0], "missing_map", None),
    }

    for case, (return_codes, error_type, failed_step) in cases.items():
        save_path_temp, trajectory_root = _configure_noobscenes_failure_case(
            tmp_path, case
        )
        log_dir = tmp_path / case / "logs"
        codes = iter(return_codes)

        def fake_run(*args, **kwargs):
            class Proc:
                returncode = next(codes)
                stdout = ""
                stderr = "failed"

            return Proc()

        monkeypatch.setattr(
            "data_juicer_agents.tools.vla.build_noobscenes_inputs.logic.subprocess.run",
            fake_run,
        )

        result = build_noobscenes_inputs(
            save_path_temp=str(save_path_temp),
            trajectory_root=str(trajectory_root),
            data_env_setup=None,
            data_python="/usr/bin/python3.8",
            dry_run=False,
            log_dir=str(log_dir),
        )

        assert result["ok"] is False
        assert result["error_type"] == error_type
        if failed_step:
            assert result["failed_step"] == failed_step
        assert _event_types(log_dir) == ["stage_start", "stage_end"]


def test_build_noobscenes_execute_accepts_prepare_finish_dataset_output_without_clip_samples(
    monkeypatch, tmp_path
):
    src = (
        tmp_path
        / "clip"
        / "20270515"
        / "seg_a"
        / "sync_data"
        / "20260515_102948_zhigu_wuhan_0"
    )
    (src / "fisheye_front").mkdir(parents=True)
    (src / "fisheye_front" / "000001.jpg").write_text("image", encoding="utf-8")
    (src / "r32_rslidar_points").mkdir()
    sensors = tmp_path / "traj" / "NoobScenes" / "params" / "20260409_U" / "sensors"
    sensors.mkdir(parents=True)
    (sensors / "front.json").write_text("{}", encoding="utf-8")

    prepare_result = prepare_finish_dataset(
        date="20270515",
        selected_segments=["seg_a"],
        scene_mode="out",
        clip_root=str(tmp_path / "clip"),
        finish_root=str(tmp_path / "finish"),
        trajectory_root=str(tmp_path / "traj"),
        sensor_params_dir=str(sensors),
        dry_run=False,
    )
    save_path_temp = tmp_path / "finish" / "20270515_temp"
    noobscenes = tmp_path / "traj" / "NoobScenes"
    _create_required_legacy_noobscenes_paths(tmp_path / "traj")
    generated = noobscenes / "v1.0-develop"
    generated.mkdir()
    (generated / "sample.json").write_text("{}", encoding="utf-8")
    (noobscenes / "maps").mkdir()
    (noobscenes / "maps" / "map.png").write_text("map", encoding="utf-8")
    log_dir = tmp_path / "logs"

    def fake_run(*args, **kwargs):
        class Proc:
            returncode = 0
            stdout = ""
            stderr = ""

        return Proc()

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.build_noobscenes_inputs.logic.subprocess.run",
        fake_run,
    )

    result = build_noobscenes_inputs(
        save_path_temp=str(save_path_temp),
        trajectory_root=str(tmp_path / "traj"),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        dry_run=False,
        log_dir=str(log_dir),
    )

    clip = save_path_temp / "samples" / "20270515" / "20260515_102948_zhigu_wuhan_0"
    assert prepare_result["ok"] is True
    assert not (clip / "samples").exists()
    assert result["ok"] is True
    assert result.get("error_type") != "noobscenes_input_validation_failed"
    assert result["video_paths"] == [str(clip / "dog.mp4")]
    assert _event_types(log_dir) == ["stage_start", "stage_end"]


def test_build_noobscenes_execute_reports_missing_legacy_paths_with_stage_end(
    tmp_path,
):
    save_path_temp = tmp_path / "finish" / "20270515_temp"
    clip = save_path_temp / "samples" / "20270515" / "20260515_102948_zhigu_wuhan_0"
    (clip / "fisheye_front").mkdir(parents=True)
    (clip / "fisheye_front" / "000001.jpg").write_text("image", encoding="utf-8")
    (clip / "r32_rslidar_points").mkdir()
    log_dir = tmp_path / "logs"

    result = build_noobscenes_inputs(
        save_path_temp=str(save_path_temp),
        trajectory_root=str(tmp_path / "missing_traj"),
        data_env_setup=None,
        data_python="/usr/bin/python3.8",
        dry_run=False,
        log_dir=str(log_dir),
    )

    assert result["ok"] is False
    assert result["error_type"] == "missing_legacy_paths"
    missing_paths = {item["path"] for item in result["missing"]}
    assert str(tmp_path / "missing_traj" / "NoobScenes") in missing_paths
    assert (
        str(tmp_path / "missing_traj" / "NoobScenes" / "include" / "0_creat_box.py")
        in missing_paths
    )
    assert (
        str(tmp_path / "missing_traj" / "0_1th_box" / "img2video.py") in missing_paths
    )
    assert _event_types(log_dir) == ["stage_start", "stage_end"]


def test_finish_tool_specs_wrap_logic_results(tmp_path):
    clip = tmp_path / "clip" / "20270515" / "seg_a" / "sync_data"
    clip.mkdir(parents=True)
    sensors = tmp_path / "traj" / "NoobScenes" / "params" / "20260409_U" / "sensors"
    sensors.mkdir(parents=True)

    list_result = VLA_LIST_CLIP_SEGMENTS.execute(
        ToolContext(working_dir=str(tmp_path)),
        {"date": "20270515", "clip_root": str(tmp_path / "clip")},
    )
    prepare_result = VLA_PREPARE_FINISH_DATASET.execute(
        ToolContext(working_dir=str(tmp_path)),
        {
            "date": "20270515",
            "selected_segments": ["seg_a"],
            "scene_mode": "out",
            "clip_root": str(tmp_path / "clip"),
            "finish_root": str(tmp_path / "finish"),
            "trajectory_root": str(tmp_path / "traj"),
            "sensor_params_dir": str(sensors),
            "dry_run": True,
            "run_id": "run_finish",
        },
    )
    noobscenes_result = VLA_BUILD_NOOBSCENES_INPUTS.execute(
        ToolContext(working_dir=str(tmp_path)),
        {
            "save_path_temp": str(tmp_path / "finish" / "20270515_temp"),
            "trajectory_root": str(tmp_path / "traj"),
            "data_env_setup": None,
            "data_python": "/usr/bin/python3.8",
            "dry_run": True,
            "run_id": "run_noob",
        },
    )

    assert list_result.ok is True
    assert list_result.data["segments"][0]["name"] == "seg_a"
    assert prepare_result.ok is False
    assert prepare_result.data["error_type"] == "no_clip_folders"
    assert noobscenes_result.ok is True
    assert VLA_LIST_CLIP_SEGMENTS.confirmation == "none"
    assert VLA_PREPARE_FINISH_DATASET.effects == "write"
    assert VLA_PREPARE_FINISH_DATASET.confirmation == "required"
    assert VLA_BUILD_NOOBSCENES_INPUTS.effects == "execute"
    assert VLA_BUILD_NOOBSCENES_INPUTS.confirmation == "required"

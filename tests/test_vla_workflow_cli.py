# -*- coding: utf-8 -*-

from __future__ import annotations

import json
from pathlib import Path

from data_juicer_agents.cli import build_parser, main


def _write_metadata(path: Path) -> None:
    path.write_text(
        """rosbag2_bagfile_information:
  version: 4
  relative_file_paths:
    - 20260515_102948_0.db3
  message_count: 15574
  topics_with_message_count:
    - topic_metadata:
        name: /lidar_points
        type: sensor_msgs/msg/PointCloud2
      message_count: 334
    - topic_metadata:
        name: /cam_video5/csi_cam/image_raw/compressed
        type: sensor_msgs/msg/CompressedImage
      message_count: 343
    - topic_metadata:
        name: /utlidar/robot_odom_systime
        type: nav_msgs/msg/Odometry
      message_count: 5136
""",
        encoding="utf-8",
    )


def _build_fake_navigation_roots(tmp_path: Path) -> dict[str, Path]:
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    finish_root = tmp_path / "finish_data"
    trajectory_root = (
        tmp_path
        / "Trajectory_visualization"
        / "Object_location_gh_v3_fisheye_five_U_add_SF_01"
    )
    segment = raw_root / "20270515" / "20260515_102948"
    segment.mkdir(parents=True)
    _write_metadata(segment / "metadata.yaml")
    (segment / "20260515_102948_0.db3").write_text("", encoding="utf-8")

    (clip_root / "20270515" / "20260515_102948" / "sync_data" / "seq0" / "grid_map").mkdir(
        parents=True
    )
    sensors = trajectory_root / "NoobScenes" / "params" / "20260409_U" / "sensors"
    sensors.mkdir(parents=True)
    (sensors / "fisheye_front.json").write_text("{}", encoding="utf-8")
    (sensors / "r32_rslidar_points.json").write_text("{}", encoding="utf-8")
    finish_root.mkdir(parents=True)

    return {
        "raw_root": raw_root,
        "clip_root": clip_root,
        "finish_root": finish_root,
        "trajectory_root": trajectory_root,
    }


def test_vla_workflow_parser_accepts_run_command():
    parser = build_parser()

    args = parser.parse_args(
        [
            "vla-workflow",
            "run",
            "--scenario",
            "navigation_vla",
            "--date",
            "20270515",
            "--segments",
            "all",
            "--scene-mode",
            "out",
            "--dry-run",
            "--run-id",
            "run-test",
        ]
    )

    assert args.command == "vla-workflow"
    assert args.vla_workflow_action == "run"
    assert args.scenario == "navigation_vla"
    assert args.date == "20270515"
    assert args.segments == "all"
    assert args.scene_mode == "out"
    assert args.dry_run is True
    assert args.run_id == "run-test"


def test_vla_workflow_dry_run_writes_planning_artifacts(
    monkeypatch,
    tmp_path: Path,
    capsys,
):
    roots = _build_fake_navigation_roots(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("VLA_RAW_ROOT", str(roots["raw_root"]))
    monkeypatch.setenv("VLA_CLIP_ROOT", str(roots["clip_root"]))
    monkeypatch.setenv("VLA_FINISH_ROOT", str(roots["finish_root"]))
    monkeypatch.setenv("VLA_TRAJECTORY_ROOT", str(roots["trajectory_root"]))

    code = main(
        [
            "vla-workflow",
            "run",
            "--scenario",
            "navigation_vla",
            "--date",
            "20270515",
            "--segments",
            "all",
            "--scene-mode",
            "out",
            "--dry-run",
            "--run-id",
            "run-test",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["action"] == "vla_workflow_run"
    assert payload["dry_run"] is True
    assert payload["status"] == "awaiting_confirmation"
    assert payload["approval_status"] == "pending"
    assert payload["approval_required"] is True

    artifacts = payload["artifacts"]
    for name in (
        "planning_notes.json",
        "observations.json",
        "data_profile.json",
        "plan.json",
    ):
        key = name.removesuffix(".json")
        assert artifacts[key].endswith(name)
        assert Path(artifacts[key]).is_file()

    assert any(item["type"] == "approval_required" for item in payload["messages"])


def test_session_prompt_prefers_vla_workflow_for_complex_navigation_requests():
    from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

    agent = DJSessionAgent(use_llm_router=False)
    prompt = agent._session_sys_prompt()

    assert "complex navigation VLA data processing should use vla_workflow capability" in prompt
    assert "legacy single ReAct VLA tool chain is only for manual recovery" in prompt

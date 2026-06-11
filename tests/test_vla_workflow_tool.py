# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec, get_tool_spec


class AnyInput(BaseModel):
    model_config = ConfigDict(extra="allow")


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


def _fake_spec(
    name: str,
    calls: list[tuple[str, dict]],
    *,
    pause_manual: bool = False,
) -> ToolSpec:
    def _execute(ctx: ToolContext, args: BaseModel) -> ToolResult:
        payload = args.model_dump()
        calls.append((name, payload))
        data = {"ok": True, "tool": name}
        if name == "vla_run_manual_box_annotation":
            data["yaml_paths"] = [] if pause_manual else ["fake.yaml"]
        return ToolResult.success(summary=f"{name} ok", data=data)

    return ToolSpec(
        name=name,
        description=f"fake {name}",
        input_model=AnyInput,
        output_model=None,
        executor=_execute,
        tags=("vla",),
        effects="execute",
    )


def _ctx(tmp_path: Path, events: list[dict] | None = None) -> ToolContext:
    runtime_values = {}
    if events is not None:
        runtime_values["emit_event"] = lambda event_type, **payload: events.append(
            {"type": event_type, **payload}
        )
    return ToolContext(
        working_dir=str(tmp_path / ".djx"),
        artifacts_dir=str(tmp_path / ".djx"),
        runtime_values=runtime_values,
    )


def _set_vla_roots(monkeypatch, roots: dict[str, Path]) -> None:
    monkeypatch.setenv("VLA_RAW_ROOT", str(roots["raw_root"]))
    monkeypatch.setenv("VLA_CLIP_ROOT", str(roots["clip_root"]))
    monkeypatch.setenv("VLA_FINISH_ROOT", str(roots["finish_root"]))
    monkeypatch.setenv("VLA_TRAJECTORY_ROOT", str(roots["trajectory_root"]))


def test_vla_run_workflow_tool_dry_run_writes_planning_artifacts_without_stages(
    monkeypatch,
    tmp_path: Path,
):
    roots = _build_fake_navigation_roots(tmp_path)
    _set_vla_roots(monkeypatch, roots)
    spec = get_tool_spec("vla_run_workflow")
    events: list[dict] = []

    result = spec.execute(
        _ctx(tmp_path, events),
        {
            "scenario": "navigation_vla",
            "date": "20270515",
            "segments": ["20260515_102948"],
            "scene_mode": "out",
            "dry_run": True,
            "approve": False,
            "run_id": "tool-dry-run",
            "agent_mode": "deterministic",
        },
    )

    payload = result.to_payload(action=spec.name)
    assert result.ok is True
    assert payload["status"] == "awaiting_confirmation"
    assert payload["stage_result_count"] == 0
    assert Path(payload["artifacts"]["planning_notes"]).is_file()
    assert Path(payload["artifacts"]["observations"]).is_file()
    assert Path(payload["artifacts"]["data_profile"]).is_file()
    assert Path(payload["artifacts"]["plan"]).is_file()
    assert not Path(payload["artifacts"]["stage_results"]).exists()
    assert [event["type"] for event in events][:3] == [
        "vla_workflow_started",
        "vla_plan_started",
        "vla_plan_completed",
    ]


def test_vla_run_workflow_tool_approve_executes_stage_loop_and_emits_progress(
    monkeypatch,
    tmp_path: Path,
):
    roots = _build_fake_navigation_roots(tmp_path)
    _set_vla_roots(monkeypatch, roots)
    calls: list[tuple[str, dict]] = []
    events: list[dict] = []

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.executor_agent.get_tool_spec",
        lambda name: _fake_spec(name, calls),
    )

    spec = get_tool_spec("vla_run_workflow")
    result = spec.execute(
        _ctx(tmp_path, events),
        {
            "date": "20270515",
            "segments": "20260515_102948",
            "scene_mode": "out",
            "approve": True,
            "run_id": "tool-execute-run",
            "agent_mode": "deterministic",
        },
    )

    payload = result.to_payload(action=spec.name)
    assert result.ok is True
    assert payload["status"] == "completed"
    assert payload["stage_result_count"] == len(calls)
    assert Path(payload["artifacts"]["stage_results"]).is_file()
    stage_events = [event for event in events if event["type"].startswith("vla_stage_")]
    assert any(event["type"] == "vla_stage_started" for event in stage_events)
    assert any(event["type"] == "vla_stage_completed" for event in stage_events)
    assert events[-1]["type"] == "vla_workflow_completed"
    assert "Executor-Agent" in payload["progress_summary"]


def test_vla_run_workflow_tool_pauses_on_missing_manual_annotation_yaml(
    monkeypatch,
    tmp_path: Path,
):
    roots = _build_fake_navigation_roots(tmp_path)
    _set_vla_roots(monkeypatch, roots)
    calls: list[tuple[str, dict]] = []
    events: list[dict] = []

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.executor_agent.get_tool_spec",
        lambda name: _fake_spec(name, calls, pause_manual=True),
    )

    spec = get_tool_spec("vla_run_workflow")
    result = spec.execute(
        _ctx(tmp_path, events),
        {
            "date": "20270515",
            "segments": ["20260515_102948"],
            "scene_mode": "out",
            "approve": True,
            "run_id": "tool-paused-run",
            "agent_mode": "deterministic",
        },
    )

    payload = result.to_payload(action=spec.name)
    assert result.ok is True
    assert payload["status"] == "paused"
    assert payload["current_stage_id"] == "manual_box_annotation"
    assert payload["stage_result_count"] == len(calls)
    assert any(event["type"] == "vla_stage_paused" for event in events)
    assert "manual_box_annotation" in payload["user_message"]

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from data_juicer_agents.capabilities.vla_workflow.catalog.navigation import (
    NAVIGATION_TOOL_CAPABILITIES,
)
from data_juicer_agents.capabilities.vla_workflow.executor_agent import execute_stage
from data_juicer_agents.capabilities.vla_workflow.graph import (
    VLAWorkflowState,
    ask_confirmation,
    generate_workflow_plan,
    initialize_state,
    plan_agent_fill_data_profile,
    plan_agent_read_docs,
    validate_data_profile,
    validate_plan_node,
)
from data_juicer_agents.capabilities.vla_workflow.plan.model import VLAWorkflowPlan
from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationVLADataProfile,
)
from data_juicer_agents.cli import main
from data_juicer_agents.commands.vla_workflow_cmd import _navigation_observations
from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.tools.vla._shared.config import VLAPaths

OBJECT_LOCATION_DIR = "Object_location_gh_v3_fisheye_five_U_add_SF_01"


def _touch(path: Path, text: str = "# fixture\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_metadata(
    path: Path, db3_name: str, topics: list[tuple[str, str, int]]
) -> None:
    topic_blocks = []
    for name, topic_type, count in topics:
        topic_blocks.append(f"""    - topic_metadata:
        name: {name}
        type: {topic_type}
      message_count: {count}""")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "rosbag2_bagfile_information:",
                "  version: 4",
                "  relative_file_paths:",
                f"    - {db3_name}",
                "  message_count: 15574",
                "  topics_with_message_count:",
                *topic_blocks,
                "",
            ]
        ),
        encoding="utf-8",
    )


def _build_fake_navigation_filesystem(
    tmp_path: Path,
    *,
    date: str,
    segment_names: list[str],
    script_variant: str,
    sensor_params_name: str,
    trajectory_script: str,
    topics: list[tuple[str, str, int]],
    existing_gridmap: bool,
    pointcloud_generator: bool = True,
) -> dict[str, Path]:
    roots = {
        "raw_root": tmp_path / "raw_data",
        "clip_root": tmp_path / "clip_data",
        "finish_root": tmp_path / "finish_data",
        "data_toolbox_src": tmp_path / "DataToolbox" / "src",
        "trajectory_root": tmp_path / "Trajectory_visualization" / OBJECT_LOCATION_DIR,
    }

    for segment in segment_names:
        raw_segment = roots["raw_root"] / date / segment
        db3_name = f"{segment}_0.db3"
        _write_metadata(raw_segment / "metadata.yaml", db3_name, topics)
        _touch(raw_segment / db3_name, "")

    if script_variant == "u_legacy_topics":
        _touch(
            roots["data_toolbox_src"]
            / "1_extract_data_from_bag_multi_process_ros2_U_legacy.py"
        )
        _touch(roots["data_toolbox_src"] / "2_sync_data_multi_process_U_legacy.py")
    else:
        _touch(
            roots["data_toolbox_src"]
            / "1_extract_data_from_bag_multi_process_ros2_U.py"
        )
        _touch(roots["data_toolbox_src"] / "2_sync_data_multi_process_U.py")

    sensors = (
        roots["trajectory_root"]
        / "NoobScenes"
        / "params"
        / sensor_params_name
        / "sensors"
    )
    _touch(sensors / "fisheye_front.json", "{}\n")
    _touch(sensors / "r32_rslidar_points.json", "{}\n")
    _touch(roots["trajectory_root"] / "2_pt_project" / trajectory_script)
    _touch(roots["trajectory_root"] / "2_pt_project" / "3_move_dir.py")

    if pointcloud_generator:
        _touch(roots["trajectory_root"] / "other_code" / "pcd_to_grid.py")
    if script_variant == "go2w_current_topics":
        _touch(roots["trajectory_root"] / "other_code" / "cp_gridmap.py")

    if existing_gridmap:
        gridmap = (
            roots["clip_root"]
            / date
            / segment_names[0]
            / "sync_data"
            / f"{segment_names[0]}_zhigu_wuhan_0"
            / "grid_map"
        )
        gridmap.mkdir(parents=True)

    roots["finish_root"].mkdir(parents=True, exist_ok=True)
    return roots


def _legacy_topics() -> list[tuple[str, str, int]]:
    return [
        ("/lidar_points", "sensor_msgs/msg/PointCloud2", 334),
        (
            "/cam_video5/csi_cam/image_raw/compressed",
            "sensor_msgs/msg/CompressedImage",
            343,
        ),
        ("/utlidar/robot_odom_systime", "nav_msgs/msg/Odometry", 5136),
    ]


def _go2w_topics() -> list[tuple[str, str, int]]:
    return [
        ("/rs32_lidar_points", "sensor_msgs/msg/PointCloud2", 334),
        (
            "/cam_video4/csi_cam/image_raw/compressed",
            "sensor_msgs/msg/CompressedImage",
            343,
        ),
        ("/sport_odom", "nav_msgs/msg/Odometry", 5136),
    ]


def _apply_roots(monkeypatch, roots: dict[str, Path]) -> None:
    monkeypatch.setenv("VLA_RAW_ROOT", str(roots["raw_root"]))
    monkeypatch.setenv("VLA_CLIP_ROOT", str(roots["clip_root"]))
    monkeypatch.setenv("VLA_FINISH_ROOT", str(roots["finish_root"]))
    monkeypatch.setenv("VLA_DATA_TOOLBOX_SRC", str(roots["data_toolbox_src"]))
    monkeypatch.setenv("VLA_TRAJECTORY_ROOT", str(roots["trajectory_root"]))


def _run_cli_dry_run(
    monkeypatch, tmp_path: Path, roots: dict[str, Path], date: str, capsys
):
    monkeypatch.chdir(tmp_path)
    _apply_roots(monkeypatch, roots)

    code = main(
        [
            "vla-workflow",
            "run",
            "--scenario",
            "navigation_vla",
            "--date",
            date,
            "--segments",
            "all",
            "--scene-mode",
            "out",
            "--dry-run",
            "--run-id",
            f"run-{date}",
            "--agent-mode",
            "deterministic",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    return code, payload


def _load_artifacts(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    data_profile = json.loads(Path(payload["artifacts"]["data_profile"]).read_text())
    plan = json.loads(Path(payload["artifacts"]["plan"]).read_text())
    return data_profile, plan


def _stage_by_kind(plan: dict[str, Any], stage_kind: str) -> dict[str, Any]:
    return {stage["stage_kind"]: stage for stage in plan["active_stages"]}[stage_kind]


def _assert_plan_has_no_tool_args(plan: dict[str, Any]) -> None:
    for stage in plan["active_stages"]:
        assert "tool_args" not in stage
        assert "tool_args_preview" not in stage
    for skipped in plan["skipped_stages"]:
        assert set(skipped) <= {"stage_kind", "reason", "evidence", "source"}


def _executor_previews(
    *,
    payload: dict[str, Any],
    data_profile: dict[str, Any],
    plan: dict[str, Any],
    roots: dict[str, Path],
    date: str,
) -> dict[str, dict[str, Any]]:
    plan_model = VLAWorkflowPlan.model_validate(plan)
    profile_model = NavigationVLADataProfile.model_validate(data_profile)
    runtime_context = {
        "dry_run": True,
        "run_id": payload["run_id"],
        "log_dir": payload["run_dir"],
        "stage_args": {
            "projection_and_trajectory": {
                "save_path": str(roots["finish_root"] / date),
                "save_path_temp": str(roots["finish_root"] / f"{date}_temp"),
            }
        },
    }
    previews: dict[str, dict[str, Any]] = {}
    for stage in plan_model.active_stages:
        if stage.stage_kind not in {
            "extract_and_sync",
            "prepare_finish_dataset",
            "gridmap_processing",
            "projection_and_trajectory",
            "validate_outputs",
        }:
            continue
        result = execute_stage(
            plan=plan_model,
            current_stage=stage,
            data_profile=profile_model,
            observations=[],
            previous_stage_outputs={},
            runtime_context=runtime_context,
            tool_context=ToolContext(
                working_dir=str(Path(payload["run_dir"])),
                artifacts_dir=str(Path(payload["run_dir"])),
            ),
        )
        previews[stage.stage_kind] = result.tool_args_preview
    return previews


def _copy_catalog(*, pointcloud_status: str):
    catalog = [item.model_copy(deep=True) for item in NAVIGATION_TOOL_CAPABILITIES]
    for capability in catalog:
        if capability.tool != "vla_prepare_gridmap":
            continue
        capability.variants = [
            (
                variant.model_copy(update={"status": pointcloud_status}, deep=True)
                if variant.id == "pointcloud_to_gridmap"
                else variant
            )
            for variant in capability.variants
        ]
    return catalog


def test_20270515_navigation_dry_run_acceptance(monkeypatch, tmp_path: Path, capsys):
    roots = _build_fake_navigation_filesystem(
        tmp_path,
        date="20270515",
        segment_names=["20260515_102948", "20260515_103111"],
        script_variant="u_legacy_topics",
        sensor_params_name="20260409_U",
        trajectory_script="2_othermethod_cjl.py",
        topics=_legacy_topics(),
        existing_gridmap=True,
    )

    code, payload = _run_cli_dry_run(monkeypatch, tmp_path, roots, "20270515", capsys)
    data_profile, plan = _load_artifacts(payload)
    previews = _executor_previews(
        payload=payload,
        data_profile=data_profile,
        plan=plan,
        roots=roots,
        date="20270515",
    )

    assert code == 0
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["status"] == "awaiting_confirmation"
    _assert_plan_has_no_tool_args(plan)
    assert _stage_by_kind(plan, "extract_and_sync")["variant"] == "u_legacy_topics"
    assert _stage_by_kind(plan, "gridmap_processing")["tool"] == "vla_prepare_gridmap"
    assert (
        _stage_by_kind(plan, "gridmap_processing")["variant"]
        == "copy_existing_artifact"
    )
    assert (
        _stage_by_kind(plan, "projection_and_trajectory")["variant"]
        == "cjl_with_gridmap"
    )
    assert _stage_by_kind(plan, "validate_outputs")["variant"] == "expect_gridmap"
    assert data_profile["sync"]["query_raw_dir"] == "lidar_points"
    assert data_profile["calibration"]["sensor_params_dir"].endswith(
        "20260409_U/sensors"
    )
    assert data_profile["gridmap"]["expect_gridmap_output"] is True

    assert previews["extract_and_sync"]["script_variant"] == "u_legacy_topics"
    assert previews["extract_and_sync"]["query_dir"] == "lidar_points"
    assert previews["prepare_finish_dataset"]["sensor_params_dir"].endswith(
        "20260409_U/sensors"
    )
    assert previews["gridmap_processing"]["gridmap_variant"] == "copy_existing_artifact"
    assert (
        previews["projection_and_trajectory"]["trajectory_variant"]
        == "cjl_with_gridmap"
    )
    assert previews["projection_and_trajectory"]["use_gridmap"] is True
    assert previews["validate_outputs"]["expect_gridmap_output"] is True


def test_20270605_navigation_dry_run_acceptance(monkeypatch, tmp_path: Path, capsys):
    roots = _build_fake_navigation_filesystem(
        tmp_path,
        date="20270605",
        segment_names=["20260605_152856", "20260605_152930"],
        script_variant="go2w_current_topics",
        sensor_params_name="20260529_go2w",
        trajectory_script="2_othermethod_cjl_0525.py",
        topics=_go2w_topics(),
        existing_gridmap=True,
    )

    code, payload = _run_cli_dry_run(monkeypatch, tmp_path, roots, "20270605", capsys)
    data_profile, plan = _load_artifacts(payload)
    previews = _executor_previews(
        payload=payload,
        data_profile=data_profile,
        plan=plan,
        roots=roots,
        date="20270605",
    )

    assert code == 0
    assert payload["ok"] is True
    _assert_plan_has_no_tool_args(plan)
    assert _stage_by_kind(plan, "extract_and_sync")["variant"] == "go2w_current_topics"
    assert _stage_by_kind(plan, "gridmap_processing")["tool"] == "vla_prepare_gridmap"
    assert (
        _stage_by_kind(plan, "gridmap_processing")["variant"]
        == "copy_existing_artifact"
    )
    assert (
        _stage_by_kind(plan, "projection_and_trajectory")["variant"]
        == "cjl_0525_with_gridmap"
    )
    assert _stage_by_kind(plan, "validate_outputs")["variant"] == "expect_gridmap"
    assert data_profile["sync"]["query_raw_dir"] == "rs32_lidar_points"
    assert data_profile["calibration"]["sensor_params_dir"].endswith(
        "20260529_go2w/sensors"
    )
    assert data_profile["gridmap"]["gridmap_source"] == "existing_gridmap_artifact"
    assert data_profile["gridmap"]["expect_gridmap_output"] is True

    assert previews["extract_and_sync"]["script_variant"] == "go2w_current_topics"
    assert previews["extract_and_sync"]["query_dir"] == "rs32_lidar_points"
    assert previews["prepare_finish_dataset"]["sensor_params_dir"].endswith(
        "20260529_go2w/sensors"
    )
    assert previews["gridmap_processing"]["gridmap_variant"] == "copy_existing_artifact"
    assert (
        previews["projection_and_trajectory"]["trajectory_variant"]
        == "cjl_0525_with_gridmap"
    )
    assert previews["projection_and_trajectory"]["use_gridmap"] is True
    assert previews["validate_outputs"]["expect_gridmap_output"] is True


def test_20270605_dry_run_uses_pointcloud_generator_without_existing_gridmap(
    monkeypatch,
    tmp_path: Path,
    capsys,
):
    roots = _build_fake_navigation_filesystem(
        tmp_path,
        date="20270605",
        segment_names=["20260605_152856", "20260605_152930"],
        script_variant="go2w_current_topics",
        sensor_params_name="20260529_go2w",
        trajectory_script="2_othermethod_cjl_0525.py",
        topics=_go2w_topics(),
        existing_gridmap=False,
        pointcloud_generator=True,
    )

    code, payload = _run_cli_dry_run(monkeypatch, tmp_path, roots, "20270605", capsys)
    data_profile, plan = _load_artifacts(payload)

    assert code == 0
    assert data_profile["gridmap"]["gridmap_source"] == "generated_from_pointcloud"
    assert _stage_by_kind(plan, "gridmap_processing")["tool"] == "vla_prepare_gridmap"
    assert (
        _stage_by_kind(plan, "gridmap_processing")["variant"] == "pointcloud_to_gridmap"
    )
    assert (
        _stage_by_kind(plan, "projection_and_trajectory")["variant"]
        == "cjl_0525_with_gridmap"
    )


def test_workflow_blocks_when_gridmap_source_and_generator_are_unavailable(
    monkeypatch,
    tmp_path: Path,
):
    roots = _build_fake_navigation_filesystem(
        tmp_path,
        date="20270605",
        segment_names=["20260605_152856", "20260605_152930"],
        script_variant="go2w_current_topics",
        sensor_params_name="20260529_go2w",
        trajectory_script="2_othermethod_cjl_0525.py",
        topics=_go2w_topics(),
        existing_gridmap=False,
        pointcloud_generator=False,
    )
    _apply_roots(monkeypatch, roots)
    catalog = _copy_catalog(pointcloud_status="placeholder")
    paths = VLAPaths()
    state = initialize_state(
        VLAWorkflowState(
            user_request="Run navigation VLA dry-run for 20270605.",
            scenario="navigation_vla",
            user_inputs={
                "scenario": "navigation_vla",
                "date": "20270605",
                "selected_segments": "all",
                "scene_mode": "out",
                "raw_root": str(paths.raw_root),
                "clip_root": str(paths.clip_root),
                "finish_root": str(paths.finish_root),
                "trajectory_root": str(paths.trajectory_root),
            },
            run_id="run-20270605-blocked",
        ),
        tool_context=ToolContext(
            working_dir=str(tmp_path / ".djx"),
            artifacts_dir=str(tmp_path / ".djx"),
        ),
    )
    state.observations = _navigation_observations(
        user_inputs=state.user_inputs,
        paths=paths,
        run_id=state.run_id,
        log_dir=state.run_dir,
    )

    state = plan_agent_read_docs(state)
    state = plan_agent_fill_data_profile(state, catalog=catalog)
    state = validate_data_profile(state)
    state = generate_workflow_plan(state, catalog=catalog)
    state = validate_plan_node(state, catalog=catalog)
    state = ask_confirmation(state)

    assert (
        state.data_profile.blocking_issues[0].type
        == "missing_gridmap_source_or_generator"
    )
    assert state.status == "failed"

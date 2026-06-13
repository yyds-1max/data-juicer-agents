from __future__ import annotations

from pathlib import Path
import json

from data_juicer_agents.capabilities.vla_workflow.plan_agent import build_observation
from data_juicer_agents.capabilities.vla_workflow.plan_agent import (
    deterministic_plan_vla_workflow,
)
from data_juicer_agents.capabilities.vla_workflow.plan.model import VLAWorkflowPlan
from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationVLADataProfile,
)
from data_juicer_agents.capabilities.vla_workflow.react_agents import _plan_sys_prompt
from data_juicer_agents.capabilities.vla_workflow.react_agents import run_plan_agent_react
from data_juicer_agents.capabilities.vla_workflow.service import execute_vla_workflow
from data_juicer_agents.capabilities.vla_workflow.service import _segments_arg
from data_juicer_agents.capabilities.vla_workflow.state import PlanAgentMemory
from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.tools.vla.run_workflow.input import RunWorkflowInput


def _ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(working_dir=str(tmp_path), artifacts_dir=str(tmp_path))


def test_default_react_mode_fails_without_silent_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_API_TOKEN", raising=False)

    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="react-missing-key",
        ),
        tool_context=_ctx(tmp_path),
    )

    assert result.exit_code == 2
    assert result.payload["ok"] is False
    assert result.payload["agent_mode"] == "react"
    assert result.payload["fallback_used"] is False
    assert result.payload["error_type"] == "react_agent_unavailable"
    assert "deterministic fallback is disabled" in result.payload["message"]


def test_react_with_deterministic_fallback_is_visible(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_API_TOKEN", raising=False)
    monkeypatch.setenv("VLA_RAW_ROOT", str(tmp_path / "raw_data"))
    monkeypatch.setenv("VLA_CLIP_ROOT", str(tmp_path / "clip_data"))
    monkeypatch.setenv("VLA_FINISH_ROOT", str(tmp_path / "finish_data"))
    monkeypatch.setenv("VLA_TRAJECTORY_ROOT", str(tmp_path / "trajectory"))

    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="fallback-visible",
            agent_mode="react-with-deterministic-fallback",
        ),
        tool_context=_ctx(tmp_path),
    )

    assert result.payload["agent_mode"] == "deterministic"
    assert result.payload["requested_agent_mode"] == "react-with-deterministic-fallback"
    assert result.payload["fallback_used"] is True
    assert "Missing API key" in result.payload["fallback_reason"]
    assert any(
        item["type"] == "react_agent_fallback" for item in result.payload["messages"]
    )
    assert "deterministic fallback" in result.payload["user_message"]


def test_explicit_deterministic_mode_uses_legacy_planning_path(tmp_path: Path):
    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="deterministic-explicit",
            agent_mode="deterministic",
        ),
        tool_context=_ctx(tmp_path),
    )

    assert result.payload["agent_mode"] == "deterministic"
    assert result.payload["requested_agent_mode"] == "deterministic"
    assert result.payload["fallback_used"] is False
    assert "fallback_reason" not in result.payload


def test_segments_arg_parses_json_encoded_list_from_session_tool_call():
    assert _segments_arg('["20260515_102948"]') == ["20260515_102948"]


def _valid_react_navigation_artifacts():
    observations = [
        build_observation(
            observation_id="obs_raw_layout",
            tool="vla_inspect_raw_layout",
            raw_result={
                "ok": True,
                "date": "20270515",
                "raw_root": "/raw",
                "raw_date_dir": "/raw/20270515",
                "raw_temp_dir": "/raw/20270515_temp",
                "segments": [
                    {
                        "name": "segment_a",
                        "path": "/raw/20270515/segment_a",
                        "has_db3": True,
                        "has_metadata_yaml": True,
                        "db3_files": ["segment_a_0.db3"],
                    }
                ],
            },
        ),
        build_observation(
            observation_id="obs_topic_schema",
            tool="vla_classify_navigation_topic_schema",
            raw_result={
                "ok": True,
                "topic_schema": "u_legacy_topics",
                "topic_mapping_variant": "cam5_lidar_points_utlidar_odom",
                "required_roles_present": True,
                "missing_required_roles": [],
                "topics": [
                    {
                        "name": "/lidar_points",
                        "type": "sensor_msgs/msg/PointCloud2",
                        "role": "lidar",
                        "canonical_dir": "r32_rslidar_points",
                    },
                    {
                        "name": "/cam_video5/csi_cam/image_raw/compressed",
                        "type": "sensor_msgs/msg/CompressedImage",
                        "role": "front_fisheye_image",
                        "canonical_dir": "fisheye_front",
                    },
                    {
                        "name": "/utlidar/robot_odom_systime",
                        "type": "nav_msgs/msg/Odometry",
                        "role": "localization_odom",
                        "canonical_dir": "odom",
                    },
                ],
            },
        ),
        build_observation(
            observation_id="obs_sync",
            tool="vla_infer_sync_policy",
            raw_result={
                "ok": True,
                "query_raw_dir": "lidar_points",
                "query_canonical_dir": "r32_rslidar_points",
            },
        ),
        build_observation(
            observation_id="obs_localization",
            tool="vla_infer_localization_policy",
            raw_result={"ok": True, "source": "odom", "requires_odom_convert": True},
        ),
        build_observation(
            observation_id="obs_calibration",
            tool="vla_inspect_calibration_assets",
            raw_result={
                "ok": True,
                "recommended_sensor_params_dir": "/trajectory/params/sensors",
                "sensor_params_status": "present",
            },
        ),
        build_observation(
            observation_id="obs_gridmap",
            tool="vla_inspect_gridmap_artifacts",
            raw_result={
                "ok": True,
                "gridmap_source": "existing_gridmap_artifact",
                "available_gridmap_artifacts": ["grid_map"],
                "artifact_locations": ["finish_temp_samples"],
                "projection_input_gridmap_ready": True,
            },
        ),
    ]
    planned = deterministic_plan_vla_workflow(
        user_inputs={
            "scenario": "navigation_vla",
            "date": "20270515",
            "selected_segments": ["segment_a"],
            "scene_mode": "out",
            "raw_root": "/raw",
            "clip_root": "/clip",
            "finish_root": "/finish",
            "trajectory_root": "/trajectory",
        },
        observations=observations,
    )
    profile = planned["data_profile"].model_dump()
    plan = planned["plan"].model_dump()
    plan["plan_id"] = "react_two_phase_plan"
    return observations, profile, plan


def test_react_plan_agent_runs_profile_phase_before_plan_phase(
    monkeypatch,
    tmp_path: Path,
):
    observations, valid_profile, valid_plan = _valid_react_navigation_artifacts()
    calls: list[dict] = []

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._build_react_agent",
        lambda **_: object(),
    )

    def fake_run_agent(_agent, payload):
        calls.append(payload)
        if payload["phase"] == "profile":
            return json.dumps(
                {
                    "planning_notes": {"status": "profile_ready"},
                    "observations": observations,
                    "profile_draft": valid_profile,
                    "plan": {"active_stages": ["must_be_ignored_in_profile_phase"]},
                    "decisions": [{"type": "profile_complete"}],
                }
            )
        return json.dumps(
            {
                "planning_notes": {"status": "plan_ready"},
                "observations": observations,
                "data_profile": {"must": "not_override_validated_profile"},
                "plan_draft": valid_plan,
                "decisions": [{"type": "plan_complete"}],
            }
        )

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._run_agent",
        fake_run_agent,
    )

    result = run_plan_agent_react(
        user_request="process one segment",
        scenario="navigation_vla",
        user_inputs={
            "scenario": "navigation_vla",
            "date": "20270515",
            "selected_segments": ["segment_a"],
            "scene_mode": "out",
            "raw_root": "/raw",
            "clip_root": "/clip",
            "finish_root": "/finish",
            "trajectory_root": "/trajectory",
        },
        planning_notes={"status": "need_inspection"},
        source_docs=["navigation_vla.md"],
        tool_context=_ctx(tmp_path),
    )

    assert [call["phase"] for call in calls] == ["profile", "plan"]
    assert calls[0]["profile_schema"]
    assert "plan_schema" not in calls[0]
    assert calls[0]["profile_draft"] == {}
    assert calls[0]["available_tools"]
    assert {"name", "description", "input_schema", "effects"}.issubset(
        calls[0]["available_tools"][0]
    )
    assert calls[1]["validated_profile"] == valid_profile
    assert calls[1]["plan_schema"]
    assert "profile_schema" not in calls[1]
    assert calls[1]["plan_draft"] == {}
    assert result["data_profile"].model_dump() == valid_profile
    assert result["plan"].model_dump() == valid_plan


def test_react_planning_state_saves_react_plan_without_regenerating(
    monkeypatch,
    tmp_path: Path,
):
    observations, valid_profile, valid_plan = _valid_react_navigation_artifacts()

    def fake_run_plan_agent_react(**kwargs):
        return {
            "memory": PlanAgentMemory(
                scenario=kwargs["scenario"],
                user_inputs=dict(kwargs["user_inputs"]),
                source_docs=list(kwargs["source_docs"]),
                planning_notes=dict(kwargs["planning_notes"]),
                observations=observations,
                profile_draft=valid_profile,
                data_profile_draft=valid_profile,
                plan_draft=valid_plan,
                current_phase="done",
                ready_to_plan=True,
            ),
            "planning_notes": dict(kwargs["planning_notes"]),
            "observations": observations,
            "data_profile": NavigationVLADataProfile.model_validate(valid_profile),
            "plan": VLAWorkflowPlan.model_validate(valid_plan),
        }

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents.run_plan_agent_react",
        fake_run_plan_agent_react,
    )

    def fail_if_generate_workflow_plan_is_called(*_args, **_kwargs):
        raise AssertionError("react planning must persist the validated plan, not regenerate it")

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.service.generate_workflow_plan",
        fail_if_generate_workflow_plan_is_called,
    )

    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="react-no-regenerate",
        ),
        tool_context=_ctx(tmp_path),
    )

    assert result.exit_code == 0
    assert result.payload["plan_id"] == valid_plan["plan_id"]
    assert result.payload["status"] == "awaiting_confirmation"


def test_react_plan_agent_repairs_invalid_profile_and_plan_draft(
    monkeypatch,
    tmp_path: Path,
):
    observations = [
        build_observation(
            observation_id="obs_raw_layout",
            tool="vla_inspect_raw_layout",
            raw_result={
                "ok": True,
                "date": "20270515",
                "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
                "raw_date_dir": "/media/heying/hy_data1/VLADatasets/raw_data/20270515",
                "raw_temp_dir": "/media/heying/hy_data1/VLADatasets/raw_data/20270515_temp",
                "segments": [
                    {
                        "name": "20260515_102948",
                        "path": "/media/heying/hy_data1/VLADatasets/raw_data/20270515/20260515_102948",
                        "has_db3": True,
                        "has_metadata_yaml": True,
                        "db3_files": ["20260515_102948_0.db3"],
                    }
                ],
            },
        ),
        build_observation(
            observation_id="obs_metadata",
            tool="vla_inspect_rosbag_metadata",
            raw_result={
                "ok": True,
                "topics": [
                    {"name": "/sport_imu", "type": "sensor_msgs/msg/Imu"},
                    {
                        "name": "/lidar_points",
                        "type": "sensor_msgs/msg/PointCloud2",
                        "role": "lidar",
                        "canonical_dir": "r32_rslidar_points",
                    },
                    {
                        "name": "/cam_video5/csi_cam/image_raw/compressed",
                        "type": "sensor_msgs/msg/CompressedImage",
                        "role": "front_fisheye_image",
                        "canonical_dir": "fisheye_front",
                    },
                    {
                        "name": "/utlidar/robot_odom_systime",
                        "type": "nav_msgs/msg/Odometry",
                        "role": "localization_odom",
                        "canonical_dir": "odom",
                    },
                ],
            },
        ),
        build_observation(
            observation_id="obs_topic_schema",
            tool="vla_classify_navigation_topic_schema",
            raw_result={
                "ok": True,
                "topic_schema": "u_legacy_topics",
                "topic_mapping_variant": "u_legacy_topics",
                "required_roles_present": True,
                "missing_required_roles": [],
                "topics": [
                    {
                        "name": "/lidar_points",
                        "type": "sensor_msgs/msg/PointCloud2",
                        "role": "lidar",
                        "canonical_dir": "r32_rslidar_points",
                    },
                    {
                        "name": "/cam_video5/csi_cam/image_raw/compressed",
                        "type": "sensor_msgs/msg/CompressedImage",
                        "role": "front_fisheye_image",
                        "canonical_dir": "fisheye_front",
                    },
                    {
                        "name": "/utlidar/robot_odom_systime",
                        "type": "nav_msgs/msg/Odometry",
                        "role": "localization_odom",
                        "canonical_dir": "odom",
                    },
                ],
            },
        ),
        build_observation(
            observation_id="obs_sync",
            tool="vla_infer_sync_policy",
            raw_result={
                "ok": True,
                "query_raw_dir": "lidar_points",
                "query_canonical_dir": "r32_rslidar_points",
                "output_dir": "sync_data",
                "sequence_suffix": "zhigu_wuhan",
            },
        ),
        build_observation(
            observation_id="obs_processing",
            tool="vla_inspect_processing_state",
            raw_result={"ok": True, "has_raw_temp": False, "has_sync_data": False},
        ),
        build_observation(
            observation_id="obs_localization",
            tool="vla_infer_localization_policy",
            raw_result={
                "ok": True,
                "source": "odom",
                "canonical_output": "odom",
                "requires_odom_convert": True,
            },
        ),
        build_observation(
            observation_id="obs_calibration",
            tool="vla_inspect_calibration_assets",
            raw_result={
                "ok": True,
                "recommended_sensor_params_dir": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01/Data/3_param",
                "sensor_params_status": "present",
            },
        ),
        build_observation(
            observation_id="obs_gridmap",
            tool="vla_inspect_gridmap_artifacts",
            raw_result={
                "ok": True,
                "raw_gridmap_topic_present": False,
                "gridmap_source": "existing_gridmap_artifact",
                "available_gridmap_artifacts": ["grid_map"],
                "artifact_locations": ["finish_temp_samples"],
                "projection_input_gridmap_ready": True,
            },
        ),
    ]
    planned = deterministic_plan_vla_workflow(
        user_inputs={
            "scenario": "navigation_vla",
            "date": "20270515",
            "selected_segments": ["20260515_102948"],
            "scene_mode": "out",
            "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
            "clip_root": "/media/heying/hy_data1/VLADatasets/clip_data",
            "finish_root": "/media/heying/hy_data1/VLADatasets/finish_data",
            "trajectory_root": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01",
        },
        observations=observations,
    )
    valid_profile = planned["data_profile"].model_dump()
    valid_plan = planned["plan"].model_dump()
    valid_plan["plan_id"] = "llm_plan_after_repair"
    invalid_payload = {
        "planning_notes": {"status": "need_inspection"},
        "observations": observations,
        "data_profile": {"date": "20270515"},
        "plan": {},
        "decisions": [{"type": "llm_partial_payload"}],
    }
    repaired_payload = {
        "planning_notes": {"status": "ready_to_plan"},
        "observations": observations,
        "data_profile": valid_profile,
        "plan": valid_plan,
        "decisions": [{"type": "llm_repaired_payload"}],
    }
    calls: list[dict] = []

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._build_react_agent",
        lambda **_: object(),
    )

    def fake_run_agent(_agent, payload):
        calls.append(payload)
        return json.dumps(invalid_payload if len(calls) == 1 else repaired_payload)

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._run_agent",
        fake_run_agent,
    )

    result = run_plan_agent_react(
        user_request="process one segment",
        scenario="navigation_vla",
        user_inputs={
            "scenario": "navigation_vla",
            "date": "20270515",
            "selected_segments": ["20260515_102948"],
            "scene_mode": "out",
            "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
            "clip_root": "/media/heying/hy_data1/VLADatasets/clip_data",
            "finish_root": "/media/heying/hy_data1/VLADatasets/finish_data",
            "trajectory_root": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01",
        },
        planning_notes={"status": "need_inspection"},
        source_docs=["navigation_vla.md"],
        tool_context=_ctx(tmp_path),
    )

    assert result["data_profile"].dataset.selected_segments == ["20260515_102948"]
    assert result["plan"].plan_id == "llm_plan_after_repair"
    assert result["plan"].active_stages
    assert [call["phase"] for call in calls] == ["profile", "profile", "plan"]
    assert calls[0]["profile_schema"]
    assert "plan_schema" not in calls[0]
    guidance_path = Path("docs/导航VLA-Plan-Agent检查工具与变体规则.md")
    guidance_markdown = guidance_path.read_text(encoding="utf-8")
    assert calls[0]["planning_guidance_markdown"] == guidance_markdown
    assert calls[1]["planning_guidance_markdown"] == guidance_markdown
    assert calls[1]["validation_feedback"]["errors"]
    assert calls[1]["validation_feedback"]["errors"][0]["target"] == "data_profile"
    assert calls[2]["validated_profile"] == valid_profile
    assert calls[2]["plan_schema"]


def test_plan_sys_prompt_prioritizes_guidance_markdown():
    prompt = _plan_sys_prompt()

    assert "必须优先遵守导航 VLA 规划规则文档的指导" in prompt
    assert "source_docs 只是引用名，不代表正文" in prompt
    assert "严格 JSON" in prompt
    assert "不要 markdown" in prompt
    assert "不要解释文字" in prompt
    assert "不要 {...} 或 [...] 占位符" in prompt


def test_react_plan_agent_records_validation_failure_after_three_repairs(
    monkeypatch,
    tmp_path: Path,
):
    observation = build_observation(
        observation_id="obs_raw_layout",
        tool="vla_inspect_raw_layout",
        raw_result={
            "ok": True,
            "date": "20270515",
            "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
            "segments": [],
        },
    )
    invalid_payload = {
        "planning_notes": {"status": "need_inspection"},
        "observations": [observation],
        "data_profile": {"date": "20270515"},
        "plan": {},
        "decisions": [{"type": "still_invalid"}],
    }
    calls: list[dict] = []

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._build_react_agent",
        lambda **_: object(),
    )

    def fake_run_agent(_agent, payload):
        calls.append(payload)
        return json.dumps(invalid_payload)

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._run_agent",
        fake_run_agent,
    )

    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="react-validation-failure",
        ),
        tool_context=_ctx(tmp_path),
    )

    observations_path = Path(result.payload["artifacts"]["observations"])
    plan_agent_steps_path = (
        tmp_path
        / "vla_workflow_runs"
        / "20270515"
        / "react-validation-failure"
        / "plan_agent_steps.jsonl"
    )
    assert result.exit_code == 2
    assert result.payload["status"] == "failed"
    assert observations_path.is_file()
    assert json.loads(observations_path.read_text(encoding="utf-8")) == [observation]
    step_records = [
        json.loads(line)
        for line in plan_agent_steps_path.read_text(encoding="utf-8").splitlines()
    ]
    assert [record["event"] for record in step_records] == [
        "profile_llm_reply",
        "profile_validation_failed",
        "profile_llm_reply",
        "profile_validation_failed",
        "profile_llm_reply",
        "profile_validation_failed",
        "profile_llm_reply",
        "profile_validation_failed",
    ]
    assert step_records[0]["attempt"] == 0
    assert step_records[-1]["remaining_repair_attempts"] == 0
    assert step_records[0]["reply_text"] == json.dumps(invalid_payload)
    assert step_records[1]["validation_feedback"]["errors"]
    assert len(calls) == 4
    assert calls[-1]["remaining_repair_attempts"] == 0
    assert any(
        message["type"] == "plan_agent_validation_failed"
        for message in result.payload["messages"]
    )


def test_react_plan_agent_feedback_is_json_serializable_for_semantic_errors(
    monkeypatch,
    tmp_path: Path,
):
    observations = [
        build_observation(
            observation_id="obs_raw_layout",
            tool="vla_inspect_raw_layout",
            raw_result={
                "ok": True,
                "date": "20270515",
                "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
                "raw_date_dir": "/media/heying/hy_data1/VLADatasets/raw_data/20270515",
                "raw_temp_dir": "/media/heying/hy_data1/VLADatasets/raw_data/20270515_temp",
                "segments": [
                    {
                        "name": "20260515_102948",
                        "path": "/media/heying/hy_data1/VLADatasets/raw_data/20270515/20260515_102948",
                        "has_db3": True,
                        "has_metadata_yaml": True,
                    }
                ],
            },
        ),
        build_observation(
            observation_id="obs_topic_schema",
            tool="vla_classify_navigation_topic_schema",
            raw_result={
                "ok": True,
                "topic_schema": "u_legacy_topics",
                "topic_mapping_variant": "u_legacy_topics",
                "required_roles_present": True,
                "missing_required_roles": [],
                "topics": [
                    {
                        "name": "/lidar_points",
                        "type": "sensor_msgs/msg/PointCloud2",
                        "role": "lidar",
                        "canonical_dir": "r32_rslidar_points",
                    },
                    {
                        "name": "/cam_video5/csi_cam/image_raw/compressed",
                        "type": "sensor_msgs/msg/CompressedImage",
                        "role": "front_fisheye_image",
                        "canonical_dir": "fisheye_front",
                    },
                    {
                        "name": "/utlidar/robot_odom_systime",
                        "type": "nav_msgs/msg/Odometry",
                        "role": "localization_odom",
                        "canonical_dir": "odom",
                    },
                ],
            },
        ),
        build_observation(
            observation_id="obs_sync",
            tool="vla_infer_sync_policy",
            raw_result={
                "ok": True,
                "query_raw_dir": "lidar_points",
                "query_canonical_dir": "r32_rslidar_points",
            },
        ),
        build_observation(
            observation_id="obs_localization",
            tool="vla_infer_localization_policy",
            raw_result={"ok": True, "source": "odom", "requires_odom_convert": True},
        ),
        build_observation(
            observation_id="obs_calibration",
            tool="vla_inspect_calibration_assets",
            raw_result={
                "ok": True,
                "recommended_sensor_params_dir": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01/Data/3_param",
                "sensor_params_status": "present",
            },
        ),
        build_observation(
            observation_id="obs_gridmap",
            tool="vla_inspect_gridmap_artifacts",
            raw_result={
                "ok": True,
                "gridmap_source": "existing_gridmap_artifact",
                "projection_input_gridmap_ready": True,
            },
        ),
    ]
    planned = deterministic_plan_vla_workflow(
        user_inputs={
            "scenario": "navigation_vla",
            "date": "20270515",
            "selected_segments": ["20260515_102948"],
            "scene_mode": "out",
            "raw_root": "/media/heying/hy_data1/VLADatasets/raw_data",
            "clip_root": "/media/heying/hy_data1/VLADatasets/clip_data",
            "finish_root": "/media/heying/hy_data1/VLADatasets/finish_data",
            "trajectory_root": "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01",
        },
        observations=observations,
    )
    invalid_plan = planned["plan"].model_dump()
    invalid_plan["active_stages"][0]["variant"] = "not_in_catalog"
    invalid_payload = {
        "planning_notes": {"status": "ready_to_plan"},
        "observations": observations,
        "data_profile": planned["data_profile"].model_dump(),
        "plan": invalid_plan,
        "decisions": [{"type": "invalid_variant"}],
    }
    calls: list[dict] = []

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._build_react_agent",
        lambda **_: object(),
    )

    def fake_run_agent(_agent, payload):
        json.dumps(payload, ensure_ascii=False)
        calls.append(payload)
        return json.dumps(invalid_payload)

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._run_agent",
        fake_run_agent,
    )

    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="react-semantic-validation-failure",
        ),
        tool_context=_ctx(tmp_path),
    )

    assert result.exit_code == 2
    assert result.payload["status"] == "failed"
    assert Path(result.payload["artifacts"]["observations"]).is_file()
    assert len(calls) == 5
    assert [call["phase"] for call in calls] == [
        "profile",
        "plan",
        "plan",
        "plan",
        "plan",
    ]
    assert calls[2]["validation_feedback"]["errors"][0]["target"] == "plan"
    assert "data_profile" not in calls[2]["validation_feedback"]
    assert "plan" not in calls[2]["validation_feedback"]


def test_react_plan_agent_saves_raw_reply_when_json_parse_fails(
    monkeypatch,
    tmp_path: Path,
):
    malformed_reply = "{\n  planning_notes: {}\n}"

    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._build_react_agent",
        lambda **_: object(),
    )
    monkeypatch.setattr(
        "data_juicer_agents.capabilities.vla_workflow.react_agents._run_agent",
        lambda _agent, _payload: malformed_reply,
    )

    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="react-json-parse-failure",
        ),
        tool_context=_ctx(tmp_path),
    )

    run_dir = (
        tmp_path
        / "vla_workflow_runs"
        / "20270515"
        / "react-json-parse-failure"
    )
    plan_agent_steps_path = run_dir / "plan_agent_steps.jsonl"
    step_records = [
        json.loads(line)
        for line in plan_agent_steps_path.read_text(encoding="utf-8").splitlines()
    ]

    assert result.exit_code == 2
    assert result.payload["error_type"] == "react_agent_unavailable"
    assert [record["event"] for record in step_records] == [
        "profile_llm_reply",
        "profile_parse_failed",
    ]
    assert step_records[0]["reply_text"] == malformed_reply
    assert step_records[1]["error_type"] == "json_decode_error"
    assert "Expecting property name enclosed in double quotes" in step_records[1]["message"]

from __future__ import annotations

import json
from datetime import datetime, timezone

from data_juicer_agents.capabilities.vla_workflow.persistence import (
    append_observation,
    build_workflow_run_dir,
    load_workflow_artifacts,
    make_workflow_run_id,
    save_data_profile,
    save_planning_notes,
    save_workflow_plan,
)
from data_juicer_agents.core.tool import ToolContext


def test_workflow_persistence_writes_and_loads_planning_artifacts(tmp_path):
    run_dir = tmp_path / "runs" / "20270605" / "vla_navigation_vla_20270605_20260610120000"

    planning_notes = {
        "notes_id": "notes_20270605_navigation_001",
        "scenario": "navigation_vla",
        "source_docs": ["navigation_vla.md"],
        "status": "need_inspection",
    }
    data_profile = {
        "schema_version": 1,
        "scenario": "navigation_vla",
        "dataset": {"date": "20270605"},
    }
    plan = {
        "plan_id": "vla_plan_20270605_001",
        "scenario": "navigation_vla",
        "status": "pending",
        "active_stages": [],
    }

    planning_path = save_planning_notes(run_dir, planning_notes)
    first_observation_path = append_observation(
        run_dir,
        {
            "observation_id": "obs_001",
            "tool": "vla_inspect_ros2_topics",
            "raw_result": {"ok": True},
            "extracted_facts": {"topic_schema": "custom_topics"},
        },
    )
    second_observation_path = append_observation(
        run_dir,
        {
            "observation_id": "obs_002",
            "tool": "vla_inspect_gridmap_artifacts",
            "raw_result": {"ok": True},
            "extracted_facts": {"has_gridmap": True},
        },
    )
    profile_path = save_data_profile(run_dir, data_profile)
    plan_path = save_workflow_plan(run_dir, plan)

    assert planning_path == run_dir / "planning_notes.json"
    assert first_observation_path == run_dir / "observations.json"
    assert second_observation_path == run_dir / "observations.json"
    assert profile_path == run_dir / "data_profile.json"
    assert plan_path == run_dir / "plan.json"

    for path in (planning_path, first_observation_path, profile_path, plan_path):
        assert path.exists()
        json.loads(path.read_text(encoding="utf-8"))

    observations = json.loads(first_observation_path.read_text(encoding="utf-8"))
    assert [item["observation_id"] for item in observations] == ["obs_001", "obs_002"]

    loaded = load_workflow_artifacts(run_dir)
    assert loaded["planning_notes"] == planning_notes
    assert loaded["observations"] == observations
    assert loaded["data_profile"] == data_profile
    assert loaded["plan"] == plan


def test_workflow_run_dir_uses_context_root_and_server_date_not_sample_path(tmp_path):
    ctx = ToolContext(
        working_dir=str(tmp_path / "local_sample" / "raw_data" / "20270101"),
        artifacts_dir=str(tmp_path / "server_artifacts"),
    )
    created_at = datetime(2026, 6, 10, 12, 34, 56, tzinfo=timezone.utc)

    run_id = make_workflow_run_id(
        scenario="navigation_vla",
        date="20270605",
        created_at=created_at,
    )
    run_dir = build_workflow_run_dir(
        ctx,
        scenario="navigation_vla",
        date="20270605",
        created_at=created_at,
    )

    assert run_id == "vla_navigation_vla_20270605_20260610123456"
    assert run_dir == (
        tmp_path
        / "server_artifacts"
        / "vla_workflow_runs"
        / "20270605"
        / "vla_navigation_vla_20270605_20260610123456"
    )
    assert run_dir.exists()
    assert "20270101" not in str(run_dir)

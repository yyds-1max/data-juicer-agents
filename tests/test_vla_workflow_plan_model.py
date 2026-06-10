from __future__ import annotations

import pytest
from pydantic import ValidationError

from data_juicer_agents.capabilities.vla_workflow.plan.model import (
    SkippedStage,
    VLAWorkflowPlan,
    VLAWorkflowStage,
)
from data_juicer_agents.capabilities.vla_workflow.templates.manipulation import (
    get_manipulation_template,
)
from data_juicer_agents.capabilities.vla_workflow.templates.navigation import (
    NAVIGATION_HUMAN_CHECKPOINTS,
    NAVIGATION_STAGE_ORDER,
    get_navigation_template,
)


def test_navigation_template_exposes_order_and_manual_checkpoint():
    assert NAVIGATION_STAGE_ORDER == [
        "inspect_raw_date",
        "check_runtime",
        "prepare_raw_temp",
        "extract_and_sync",
        "list_clip_segments",
        "prepare_finish_dataset",
        "build_noobscenes_inputs",
        "manual_box_annotation",
        "run_tracking",
        "gridmap_processing",
        "projection_and_trajectory",
        "validate_outputs",
    ]
    assert NAVIGATION_HUMAN_CHECKPOINTS == [
        {"stage_kind": "manual_box_annotation", "type": "gui_annotation"}
    ]

    template = get_navigation_template()
    assert template["scenario"] == "navigation_vla"
    assert template["stage_order"] == NAVIGATION_STAGE_ORDER
    assert template["human_checkpoints"] == NAVIGATION_HUMAN_CHECKPOINTS


def test_manipulation_template_is_explicitly_unsupported():
    template = get_manipulation_template()

    assert template["scenario"] == "manipulation_vla"
    assert template["status"] == "unsupported"
    assert "navigation_vla" in template["message"]


def test_workflow_plan_model_contains_stages_not_tool_args():
    stage = VLAWorkflowStage(
        id="extract_and_sync",
        stage_kind="extract_and_sync",
        tool="vla_extract_and_sync",
        variant="u_legacy_topics",
        effects="execute",
        decision_ref="data_profile.stage_variants.extract_and_sync",
    )
    plan = VLAWorkflowPlan(
        plan_id="vla_plan_20270515_001",
        scenario="navigation_vla",
        status="pending",
        planning_notes_ref="planning_notes.json",
        observations_ref="observations.json",
        data_profile_ref="data_profile.json",
        active_stages=[stage],
    )

    payload = plan.model_dump()
    assert "active_stages" in payload
    assert "tool_args" not in payload["active_stages"][0]
    assert "tool_args_preview" not in payload["active_stages"][0]
    assert plan.approval_required is True


def test_workflow_stage_rejects_tool_arguments():
    with pytest.raises(ValidationError):
        VLAWorkflowStage(
            id="extract_and_sync",
            stage_kind="extract_and_sync",
            tool="vla_extract_and_sync",
            variant="u_legacy_topics",
            effects="execute",
            tool_args={"date": "20270515"},
        )


def test_skipped_stage_records_reason_and_optional_evidence():
    skipped = SkippedStage(
        stage_kind="manual_box_annotation",
        reason="annotation_yaml_already_exists",
        evidence=["obs_processing_state"],
        source="previous_artifacts",
    )

    assert skipped.reason == "annotation_yaml_already_exists"
    assert skipped.evidence == ["obs_processing_state"]

from __future__ import annotations

from data_juicer_agents.capabilities.vla_workflow.plan.model import (
    SkippedStage,
    VLAWorkflowPlan,
    VLAWorkflowStage,
)
from data_juicer_agents.capabilities.vla_workflow.plan.validate import validate_plan


def _stage(
    stage_kind: str,
    tool: str,
    variant: str = "default",
    effects: str = "execute",
) -> VLAWorkflowStage:
    return VLAWorkflowStage(
        id=stage_kind,
        stage_kind=stage_kind,
        tool=tool,
        variant=variant,
        effects=effects,
        decision_ref=f"data_profile.stage_variants.{stage_kind}",
    )


def _plan(
    stages: list[VLAWorkflowStage],
    *,
    skipped_stages: list[SkippedStage] | None = None,
    scenario: str = "navigation_vla",
) -> VLAWorkflowPlan:
    return VLAWorkflowPlan(
        plan_id="vla_plan_test",
        scenario=scenario,
        status="pending",
        planning_notes_ref="planning_notes.json",
        observations_ref="observations.json",
        data_profile_ref="data_profile.json",
        active_stages=stages,
        skipped_stages=skipped_stages or [],
    )


def _minimal_20270515_plan() -> VLAWorkflowPlan:
    return _plan(
        [
            _stage("inspect_raw_date", "vla_inspect_raw_date", effects="read"),
            _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics"),
            _stage("run_tracking", "vla_run_tracking"),
            _stage(
                "gridmap_processing",
                "vla_prepare_gridmap",
                "copy_existing_artifact",
            ),
            _stage(
                "projection_and_trajectory",
                "vla_run_projection_and_trajectory",
                "cjl_with_gridmap",
            ),
            _stage("validate_outputs", "vla_validate_outputs", "expect_gridmap", "read"),
        ]
    )


def _minimal_20270605_plan() -> VLAWorkflowPlan:
    return _plan(
        [
            _stage("extract_and_sync", "vla_extract_and_sync", "go2w_current_topics"),
            _stage("run_tracking", "vla_run_tracking"),
            _stage(
                "gridmap_processing",
                "vla_prepare_gridmap",
                "copy_existing_artifact",
            ),
            _stage(
                "projection_and_trajectory",
                "vla_run_projection_and_trajectory",
                "cjl_0525_with_gridmap",
            ),
            _stage("validate_outputs", "vla_validate_outputs", "expect_gridmap", "read"),
        ]
    )


def test_validate_plan_accepts_20270515_with_gridmap_plan():
    result = validate_plan(_minimal_20270515_plan())

    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_plan_accepts_20270605_gridmap_0525_plan():
    result = validate_plan(_minimal_20270605_plan())

    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_plan_rejects_fabricated_tool():
    plan = _plan([_stage("extract_and_sync", "vla_made_up_tool", "u_legacy_topics")])

    result = validate_plan(plan)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "unknown_tool"


def test_validate_plan_rejects_fabricated_variant():
    plan = _plan([_stage("extract_and_sync", "vla_extract_and_sync", "made_up")])

    result = validate_plan(plan)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "unknown_or_unavailable_variant"


def test_validate_plan_rejects_stage_order_inversion():
    plan = _plan(
        [
            _stage("run_tracking", "vla_run_tracking"),
            _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics"),
        ]
    )

    result = validate_plan(plan)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "invalid_stage_order"


def test_validate_plan_rejects_duplicate_stage_kind():
    plan = _plan(
        [
            _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics"),
            _stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics"),
        ]
    )

    result = validate_plan(plan)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "duplicate_stage_kind"


def test_validate_plan_rejects_projection_before_gridmap_processing():
    plan = _plan(
        [
            _stage("run_tracking", "vla_run_tracking"),
            _stage(
                "projection_and_trajectory",
                "vla_run_projection_and_trajectory",
                "cjl_with_gridmap",
            ),
            _stage(
                "gridmap_processing",
                "vla_prepare_gridmap",
                "copy_existing_artifact",
            ),
        ]
    )

    result = validate_plan(plan)

    assert result["ok"] is False
    assert any(error["type"] == "invalid_gridmap_stage_order" for error in result["errors"])


def test_validate_plan_rejects_skipped_stage_without_reason():
    plan = _plan(
        [_stage("validate_outputs", "vla_validate_outputs", "expect_gridmap", "read")],
        skipped_stages=[SkippedStage(stage_kind="manual_box_annotation", reason="")],
    )

    result = validate_plan(plan)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "skipped_stage_missing_reason"


def test_validate_plan_warns_when_skipped_stage_lacks_evidence():
    plan = _plan(
        [_stage("validate_outputs", "vla_validate_outputs", "expect_gridmap", "read")],
        skipped_stages=[
            SkippedStage(
                stage_kind="manual_box_annotation",
                reason="annotation_yaml_already_exists",
            )
        ],
    )

    result = validate_plan(plan)

    assert result["ok"] is True
    assert result["warnings"][0]["type"] == "skipped_stage_missing_evidence"


def test_validate_plan_requires_precise_reason_when_skipping_gridmap_processing():
    plan = _plan(
        [
            _stage(
                "projection_and_trajectory",
                "vla_run_projection_and_trajectory",
                "cjl_with_gridmap",
            ),
            _stage("validate_outputs", "vla_validate_outputs", "expect_gridmap", "read"),
        ],
        skipped_stages=[
            SkippedStage(
                stage_kind="gridmap_processing",
                reason="not_needed",
                evidence=["obs_gridmap_artifacts"],
            )
        ],
    )

    result = validate_plan(plan)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "invalid_gridmap_skip_reason"


def test_validate_plan_rejects_tool_for_wrong_stage_kind():
    plan = _plan([_stage("gridmap_processing", "vla_extract_and_sync", "u_legacy_topics")])

    result = validate_plan(plan)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "tool_stage_kind_mismatch"


def test_manipulation_scenario_cannot_enter_execution():
    plan = _plan(
        [_stage("extract_and_sync", "vla_extract_and_sync", "u_legacy_topics")],
        scenario="manipulation_vla",
    )

    result = validate_plan(plan)

    assert result["ok"] is False
    assert result["errors"][0]["type"] == "unsupported_scenario_has_active_stages"

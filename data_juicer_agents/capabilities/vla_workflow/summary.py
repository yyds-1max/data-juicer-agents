from __future__ import annotations

from data_juicer_agents.capabilities.vla_workflow.plan.model import VLAWorkflowPlan
from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationVLADataProfile,
)


def summarize_navigation_profile(profile: NavigationVLADataProfile) -> dict[str, object]:
    return {
        "scenario": profile.scenario,
        "date": profile.dataset.date,
        "topic_schema": profile.topics.topic_schema,
        "sync_query_raw_dir": profile.sync.query_raw_dir,
        "gridmap_source": profile.gridmap.gridmap_source,
        "blocking_issues": [issue.type for issue in profile.blocking_issues],
    }


def summarize_workflow_plan(plan: VLAWorkflowPlan) -> dict[str, object]:
    return {
        "plan_id": plan.plan_id,
        "scenario": plan.scenario,
        "approval_required": plan.approval_required,
        "active_stages": [
            {
                "stage_kind": stage.stage_kind,
                "tool": stage.tool,
                "variant": stage.variant,
                "effects": stage.effects,
            }
            for stage in plan.active_stages
        ],
        "skipped_stages": [
            {
                "stage_kind": skipped.stage_kind,
                "reason": skipped.reason,
                "evidence": list(skipped.evidence),
            }
            for skipped in plan.skipped_stages
        ],
    }


__all__ = ["summarize_navigation_profile", "summarize_workflow_plan"]

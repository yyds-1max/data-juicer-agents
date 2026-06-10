from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from data_juicer_agents.capabilities.vla_workflow.catalog.model import (
    ToolCapability,
    ToolVariant,
)
from data_juicer_agents.capabilities.vla_workflow.catalog.service import (
    list_tool_capabilities,
)
from data_juicer_agents.capabilities.vla_workflow.templates.navigation import (
    NAVIGATION_STAGE_ORDER,
)

from .model import SkippedStage, VLAWorkflowPlan, VLAWorkflowStage


def _issue(issue_type: str, message: str, **details: Any) -> dict[str, Any]:
    issue = {"type": issue_type, "message": message}
    if details:
        issue["details"] = details
    return issue


def _catalog_by_tool(catalog: Iterable[ToolCapability]) -> dict[str, ToolCapability]:
    return {capability.tool: capability for capability in catalog}


def _find_variant(
    capability: ToolCapability,
    variant_id: str,
) -> ToolVariant | None:
    for variant in capability.variants:
        if variant.id == variant_id:
            return variant
    return None


def _validate_stage_order(
    stages: list[VLAWorkflowStage],
    errors: list[dict[str, Any]],
) -> None:
    previous_index = -1
    seen_stage_kinds: set[str] = set()
    for stage in stages:
        if stage.stage_kind in seen_stage_kinds:
            errors.append(
                _issue(
                    "duplicate_stage_kind",
                    "active stages must be a subsequence of the workflow skeleton",
                    stage_kind=stage.stage_kind,
                )
            )
            return
        seen_stage_kinds.add(stage.stage_kind)

        try:
            stage_index = NAVIGATION_STAGE_ORDER.index(stage.stage_kind)
        except ValueError:
            errors.append(
                _issue(
                    "unknown_stage_kind",
                    f"stage_kind is not in the navigation skeleton: {stage.stage_kind}",
                    stage_kind=stage.stage_kind,
                )
            )
            continue

        if stage_index < previous_index:
            errors.append(
                _issue(
                    "invalid_stage_order",
                    "active stages must follow the navigation skeleton order",
                    stage_kind=stage.stage_kind,
                )
            )
            return
        previous_index = stage_index


def _stage_positions(stages: list[VLAWorkflowStage]) -> dict[str, int]:
    return {stage.stage_kind: index for index, stage in enumerate(stages)}


def _validate_gridmap_position(
    stages: list[VLAWorkflowStage],
    errors: list[dict[str, Any]],
) -> None:
    positions = _stage_positions(stages)
    gridmap_position = positions.get("gridmap_processing")
    if gridmap_position is None:
        return

    run_tracking_position = positions.get("run_tracking")
    if run_tracking_position is not None and gridmap_position <= run_tracking_position:
        errors.append(
            _issue(
                "invalid_gridmap_stage_order",
                "gridmap_processing must run after run_tracking",
            )
        )

    projection_position = positions.get("projection_and_trajectory")
    if projection_position is not None and gridmap_position >= projection_position:
        errors.append(
            _issue(
                "invalid_gridmap_stage_order",
                "gridmap_processing must run before projection_and_trajectory",
            )
        )


def _validate_stage_capabilities(
    stages: list[VLAWorkflowStage],
    catalog_by_tool: dict[str, ToolCapability],
    errors: list[dict[str, Any]],
) -> None:
    for stage in stages:
        capability = catalog_by_tool.get(stage.tool)
        if capability is None or capability.implementation_status != "available":
            errors.append(
                _issue(
                    "unknown_tool",
                    f"tool is not available in the capability catalog: {stage.tool}",
                    tool=stage.tool,
                )
            )
            continue

        if capability.stage_kind != stage.stage_kind:
            errors.append(
                _issue(
                    "tool_stage_kind_mismatch",
                    "tool is not allowed for the requested stage_kind",
                    tool=stage.tool,
                    expected_stage_kind=capability.stage_kind,
                    actual_stage_kind=stage.stage_kind,
                )
            )
            continue

        variant = _find_variant(capability, stage.variant)
        if variant is None or variant.status != "available":
            errors.append(
                _issue(
                    "unknown_or_unavailable_variant",
                    "variant is not available for the selected tool",
                    tool=stage.tool,
                    variant=stage.variant,
                )
            )


def _validate_skipped_stages(
    skipped_stages: list[SkippedStage],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    for skipped in skipped_stages:
        if not skipped.reason:
            errors.append(
                _issue(
                    "skipped_stage_missing_reason",
                    "skipped stage must record a reason",
                    stage_kind=skipped.stage_kind,
                )
            )
            continue

        if skipped.stage_kind == "gridmap_processing" and (
            skipped.reason != "grid_map_already_prepared"
        ):
            errors.append(
                _issue(
                    "invalid_gridmap_skip_reason",
                    "gridmap_processing can only be skipped when grid_map is already prepared",
                    reason=skipped.reason,
                )
            )

        if not skipped.evidence:
            warnings.append(
                _issue(
                    "skipped_stage_missing_evidence",
                    "skipped stage should record evidence",
                    stage_kind=skipped.stage_kind,
                )
            )


def validate_plan(
    plan: VLAWorkflowPlan,
    *,
    catalog: Iterable[ToolCapability] | None = None,
) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if plan.scenario == "manipulation_vla":
        if plan.active_stages:
            errors.append(
                _issue(
                    "unsupported_scenario_has_active_stages",
                    "manipulation_vla is unsupported and must not produce active stages",
                )
            )
        _validate_skipped_stages(plan.skipped_stages, errors, warnings)
        return {"ok": not errors, "errors": errors, "warnings": warnings}

    if catalog is None:
        catalog = list_tool_capabilities(scenario=plan.scenario)
    catalog_by_tool = _catalog_by_tool(catalog)

    _validate_stage_order(plan.active_stages, errors)
    _validate_gridmap_position(plan.active_stages, errors)
    _validate_stage_capabilities(plan.active_stages, catalog_by_tool, errors)
    _validate_skipped_stages(plan.skipped_stages, errors, warnings)

    return {"ok": not errors, "errors": errors, "warnings": warnings}


__all__ = ["validate_plan"]

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from data_juicer_agents.capabilities.vla_workflow.catalog.model import ToolCapability
from data_juicer_agents.capabilities.vla_workflow.catalog.service import (
    list_tool_capabilities,
)
from data_juicer_agents.capabilities.vla_workflow.plan.model import (
    SkippedStage,
    VLAWorkflowPlan,
    VLAWorkflowStage,
)
from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationCalibrationProfile,
    NavigationDatasetProfile,
    NavigationGridmapProfile,
    NavigationLocalizationProfile,
    NavigationProcessingState,
    NavigationSyncProfile,
    NavigationTopicsProfile,
    NavigationVLADataProfile,
    ProfileIssue,
    RawSegmentProfile,
    RawTopicProfile,
    StageVariantDecision,
)
from data_juicer_agents.capabilities.vla_workflow.state import PlanAgentMemory


NAVIGATION_RULE_DOC = "navigation_vla.md"
_PLAN_REFS = {
    "planning_notes_ref": "planning_notes.json",
    "observations_ref": "observations.json",
    "data_profile_ref": "data_profile.json",
}

_STAGE_TOOL_DEFAULTS: dict[str, tuple[str, str]] = {
    "inspect_raw_date": ("vla_inspect_raw_date", "default"),
    "check_runtime": ("vla_check_runtime", "default"),
    "prepare_raw_temp": ("vla_prepare_raw_temp", "default"),
    "extract_and_sync": ("vla_extract_and_sync", "u_legacy_topics"),
    "list_clip_segments": ("vla_list_clip_segments", "default"),
    "prepare_finish_dataset": ("vla_prepare_finish_dataset", "explicit_sensor_params"),
    "build_noobscenes_inputs": ("vla_build_noobscenes_inputs", "odom_convert_resize"),
    "manual_box_annotation": ("vla_run_manual_box_annotation", "default"),
    "run_tracking": ("vla_run_tracking", "default"),
    "gridmap_processing": ("vla_prepare_gridmap", "copy_existing_artifact"),
    "projection_and_trajectory": (
        "vla_run_projection_and_trajectory",
        "cjl_with_gridmap",
    ),
    "validate_outputs": ("vla_validate_outputs", "expect_gridmap"),
}


def build_planning_notes(
    *,
    user_inputs: Mapping[str, Any],
    scenario: str = "navigation_vla",
    source_docs: list[str] | None = None,
) -> dict[str, Any]:
    date = str(user_inputs.get("date") or "unknown")
    docs = source_docs or ([NAVIGATION_RULE_DOC] if scenario == "navigation_vla" else [])
    return {
        "notes_id": f"notes_{date}_{scenario}_001",
        "scenario": scenario,
        "source_docs": docs,
        "user_inputs": dict(user_inputs),
        "understood_rules": _understood_rules(scenario),
        "required_observations": _required_observations(scenario),
        "unknowns": _required_observations(scenario),
        "status": "need_inspection" if scenario == "navigation_vla" else "unsupported",
    }


def build_observation(
    *,
    observation_id: str,
    tool: str,
    args: Mapping[str, Any] | None = None,
    raw_result: Mapping[str, Any] | None = None,
    extracted_facts: Mapping[str, Any] | None = None,
    extraction_rationale: list[str] | None = None,
    used_for: list[str] | None = None,
) -> dict[str, Any]:
    raw = dict(raw_result or {})
    return {
        "observation_id": observation_id,
        "tool": tool,
        "args": dict(args or {}),
        "raw_result": raw,
        "extracted_facts": dict(extracted_facts or raw),
        "extraction_rationale": extraction_rationale or [],
        "used_for": used_for or [],
    }


def deterministic_plan_vla_workflow(
    *,
    user_inputs: Mapping[str, Any],
    observations: list[dict[str, Any]] | None = None,
    catalog: Iterable[ToolCapability] | None = None,
) -> dict[str, Any]:
    scenario = str(user_inputs.get("scenario") or "navigation_vla")
    memory = PlanAgentMemory(
        scenario=scenario,
        user_inputs=dict(user_inputs),
        source_docs=[NAVIGATION_RULE_DOC] if scenario == "navigation_vla" else [],
        observations=list(observations or []),
    )
    memory.planning_notes = build_planning_notes(
        user_inputs=user_inputs,
        scenario=scenario,
        source_docs=memory.source_docs,
    )

    if scenario == "manipulation_vla":
        plan = _unsupported_manipulation_plan(user_inputs)
        memory.decisions.append(
            {
                "type": "unsupported_scenario",
                "scenario": scenario,
                "message": "manipulation_vla is not implemented in the first workflow release.",
            }
        )
        return {
            "memory": memory,
            "planning_notes": memory.planning_notes,
            "observations": observations or [],
            "data_profile": None,
            "plan": plan,
        }

    if scenario != "navigation_vla":
        raise ValueError(f"unsupported VLA workflow scenario: {scenario}")

    resolved_catalog = list(catalog) if catalog is not None else list_tool_capabilities(
        scenario="navigation_vla"
    )
    profile = build_navigation_data_profile(
        user_inputs=user_inputs,
        observations=observations or [],
        catalog=resolved_catalog,
    )
    memory.data_profile_draft = profile.model_dump()
    memory.ready_to_plan = not profile.blocking_issues
    plan = generate_navigation_workflow_plan(
        profile=profile,
        catalog=resolved_catalog,
        plan_id=_plan_id(user_inputs, profile),
    )
    memory.decisions.append(
        {
            "type": "generated_plan",
            "active_stage_count": len(plan.active_stages),
            "skipped_stage_count": len(plan.skipped_stages),
            "blocked": bool(profile.blocking_issues),
        }
    )
    return {
        "memory": memory,
        "planning_notes": memory.planning_notes,
        "observations": observations or [],
        "data_profile": profile,
        "plan": plan,
    }


def build_navigation_data_profile(
    *,
    user_inputs: Mapping[str, Any],
    observations: list[dict[str, Any]],
    catalog: Iterable[ToolCapability] | None = None,
) -> NavigationVLADataProfile:
    resolved_catalog = (
        list(catalog)
        if catalog is not None
        else list_tool_capabilities(scenario="navigation_vla")
    )
    facts_by_tool = _facts_by_tool(observations)
    all_facts = _merged_facts(observations)

    raw_layout = facts_by_tool.get("vla_inspect_raw_layout", {})
    metadata = facts_by_tool.get("vla_inspect_rosbag_metadata", {})
    topic_schema = facts_by_tool.get("vla_classify_navigation_topic_schema", {})
    sync_policy = facts_by_tool.get("vla_infer_sync_policy", {})
    processing = facts_by_tool.get("vla_inspect_processing_state", {})
    calibration = facts_by_tool.get("vla_inspect_calibration_assets", {})
    localization = facts_by_tool.get("vla_infer_localization_policy", {})
    gridmap = facts_by_tool.get("vla_inspect_gridmap_artifacts", {})

    date = str(user_inputs.get("date") or raw_layout.get("date") or all_facts.get("date") or "")
    raw_root = str(user_inputs.get("raw_root") or raw_layout.get("raw_root") or "")
    raw_date_dir = str(raw_layout.get("raw_date_dir") or _join(raw_root, date))
    raw_work_dir = str(raw_layout.get("raw_temp_dir") or _join(raw_root, f"{date}_temp"))
    clip_root = str(user_inputs.get("clip_root") or "")
    finish_root = str(user_inputs.get("finish_root") or "")
    trajectory_root = str(
        user_inputs.get("trajectory_root")
        or calibration.get("trajectory_root")
        or facts_by_tool.get("vla_inspect_trajectory_script_variants", {}).get("trajectory_root")
        or ""
    )

    topics = topic_schema.get("topics") or metadata.get("topics") or all_facts.get("topics") or []
    raw_topics = [RawTopicProfile.model_validate(topic) for topic in topics]
    selected_segments = _selected_segments(user_inputs, raw_layout)
    raw_segments = [
        RawSegmentProfile.model_validate(segment)
        for segment in raw_layout.get("segments", [])
    ]

    topic_schema_value = str(topic_schema.get("topic_schema") or "unknown_topics")
    processing_state = NavigationProcessingState(
        has_raw_temp=bool(
            raw_layout.get("processing_state", {}).get("has_raw_temp")
            or processing.get("has_raw_temp", False)
        ),
        has_sync_data=bool(processing.get("has_sync_data", False)),
        sync_data_segments=list(processing.get("sync_data_segments", [])),
        has_finish_temp_samples=bool(processing.get("has_finish_temp_samples", False)),
        has_annotation_yaml=bool(processing.get("has_annotation_yaml", False)),
        has_tracking_outputs=bool(processing.get("has_tracking_outputs", False)),
        has_project_npy=bool(processing.get("has_project_npy", False)),
        has_final_outputs=bool(processing.get("has_final_outputs", False)),
        has_final_grid_map=bool(processing.get("has_final_grid_map", False)),
    )

    profile = NavigationVLADataProfile(
        dataset=NavigationDatasetProfile(
            date=date,
            raw_root=raw_root,
            raw_date_dir=raw_date_dir,
            raw_work_dir=raw_work_dir,
            clip_root=clip_root,
            finish_root=finish_root,
            trajectory_root=trajectory_root,
            scene_mode=str(user_inputs.get("scene_mode") or "unknown"),
            selected_segments=selected_segments,
        ),
        raw_segments=raw_segments,
        topics=NavigationTopicsProfile(
            raw_topics=raw_topics,
            topic_schema=topic_schema_value,
            topic_mapping_variant=str(topic_schema.get("topic_mapping_variant") or ""),
            required_roles_present=bool(topic_schema.get("required_roles_present", False)),
            missing_required_roles=list(topic_schema.get("missing_required_roles", [])),
        ),
        sync=NavigationSyncProfile(
            query_raw_dir=str(sync_policy.get("query_raw_dir") or _default_sync_dir(topic_schema_value)),
            query_canonical_dir=str(
                sync_policy.get("query_canonical_dir") or "r32_rslidar_points"
            ),
            output_dir=str(sync_policy.get("output_dir") or "sync_data"),
            sequence_suffix=str(sync_policy.get("sequence_suffix") or "zhigu_wuhan"),
        ),
        processing_state=processing_state,
        localization=NavigationLocalizationProfile(
            source=str(localization.get("source") or "unknown"),
            canonical_output=str(localization.get("canonical_output") or ""),
            requires_odom_convert=bool(localization.get("requires_odom_convert", False)),
            requires_cp_ins=bool(localization.get("requires_cp_ins", False)),
        ),
        calibration=NavigationCalibrationProfile(
            platform_hint=str(user_inputs.get("platform_hint") or ""),
            sensor_params_dir=str(calibration.get("recommended_sensor_params_dir") or ""),
            sensor_params_status=str(calibration.get("sensor_params_status") or "unknown"),
        ),
        gridmap=NavigationGridmapProfile(
            raw_gridmap_topic_present=bool(gridmap.get("raw_gridmap_topic_present", False)),
            gridmap_source=str(gridmap.get("gridmap_source") or "unknown"),
            requires_gridmap_processing=bool(
                gridmap.get("gridmap_source") != "unknown"
                and not gridmap.get("projection_input_gridmap_ready", False)
            ),
            expect_gridmap_output=True,
            available_gridmap_artifacts=list(gridmap.get("available_gridmap_artifacts", [])),
            artifact_locations=list(gridmap.get("artifact_locations", [])),
            projection_input_gridmap_ready=bool(
                gridmap.get("projection_input_gridmap_ready", False)
            ),
            reason="navigation workflow requires final grid_map output",
        ),
        evidence=_evidence_from_observations(observations),
    )

    _apply_stage_variant_decisions(profile, resolved_catalog)
    _apply_blocking_issues(profile, facts_by_tool, resolved_catalog)
    return profile


def generate_navigation_workflow_plan(
    *,
    profile: NavigationVLADataProfile,
    catalog: Iterable[ToolCapability] | None = None,
    plan_id: str | None = None,
) -> VLAWorkflowPlan:
    if profile.blocking_issues:
        return VLAWorkflowPlan(
            plan_id=plan_id or _plan_id({}, profile),
            scenario="navigation_vla",
            status="failed",
            active_stages=[],
            skipped_stages=[],
            approval_required=False,
            **_PLAN_REFS,
        )

    active: list[VLAWorkflowStage] = []
    skipped: list[SkippedStage] = []
    stages_to_skip = _skip_decisions(profile)
    capabilities = _catalog_by_stage(catalog or list_tool_capabilities(scenario="navigation_vla"))

    for stage_kind in _STAGE_TOOL_DEFAULTS:
        if stage_kind in stages_to_skip:
            skipped.append(stages_to_skip[stage_kind])
            continue
        tool, default_variant = _STAGE_TOOL_DEFAULTS[stage_kind]
        capability = capabilities.get(stage_kind)
        if capability is not None:
            tool = capability.tool
        decision = profile.stage_variants.get(stage_kind)
        variant = decision.variant if decision is not None else default_variant
        effects = capability.effects if capability is not None else _default_effect(stage_kind)
        active.append(
            VLAWorkflowStage(
                id=stage_kind,
                stage_kind=stage_kind,
                tool=tool,
                variant=variant,
                effects=effects,
                decision_ref=(
                    f"data_profile.stage_variants.{stage_kind}"
                    if decision is not None
                    else None
                ),
            )
        )

    return VLAWorkflowPlan(
        plan_id=plan_id or _plan_id({}, profile),
        scenario="navigation_vla",
        status="pending",
        active_stages=active,
        skipped_stages=skipped,
        approval_required=any(stage.effects in {"write", "execute", "external"} for stage in active),
        **_PLAN_REFS,
    )


def _apply_stage_variant_decisions(
    profile: NavigationVLADataProfile,
    catalog: Iterable[ToolCapability],
) -> None:
    topic_schema = profile.topics.topic_schema
    profile.stage_variants["extract_and_sync"] = StageVariantDecision(
        variant=(
            topic_schema
            if topic_schema in {"u_legacy_topics", "go2w_current_topics"}
            else "custom_topic_mapping"
        ),
        reason=f"raw topic schema classified as {topic_schema}",
        evidence=profile.evidence.get("topics.topic_schema", []),
    )
    profile.stage_variants["prepare_finish_dataset"] = StageVariantDecision(
        variant="explicit_sensor_params",
        reason="sensor params are selected as an explicit path",
        evidence=profile.evidence.get("calibration.sensor_params_dir", []),
    )
    profile.stage_variants["build_noobscenes_inputs"] = StageVariantDecision(
        variant=_localization_variant(profile.localization.source),
        reason=f"localization source is {profile.localization.source}",
        evidence=profile.evidence.get("localization.source", []),
    )
    profile.stage_variants["projection_and_trajectory"] = StageVariantDecision(
        variant=(
            "cjl_0525_with_gridmap"
            if topic_schema == "go2w_current_topics"
            else "cjl_with_gridmap"
        ),
        reason="navigation projection consumes a prepared grid_map",
        evidence=profile.evidence.get("topics.topic_schema", []),
    )
    profile.stage_variants["validate_outputs"] = StageVariantDecision(
        variant="expect_gridmap",
        reason="navigation final outputs must include grid_map",
        evidence=profile.evidence.get("gridmap.expect_gridmap_output", []),
    )

    if profile.gridmap.projection_input_gridmap_ready:
        return

    if profile.gridmap.gridmap_source in {"raw_topic", "existing_gridmap_artifact"}:
        profile.gridmap.requires_gridmap_processing = True
        profile.stage_variants["gridmap_processing"] = StageVariantDecision(
            variant="copy_existing_artifact",
            reason="grid_map artifact exists and must be prepared for projection input",
            evidence=profile.evidence.get("gridmap.gridmap_source", []),
        )
        return

    if _variant_available(catalog, "vla_prepare_gridmap", "pointcloud_to_gridmap"):
        profile.gridmap.gridmap_source = "generated_from_pointcloud"
        profile.gridmap.requires_gridmap_processing = True
        profile.stage_variants["gridmap_processing"] = StageVariantDecision(
            variant="pointcloud_to_gridmap",
            reason="no existing grid_map artifact; pointcloud generator is available",
            evidence=profile.evidence.get("gridmap.gridmap_source", []),
        )


def _apply_blocking_issues(
    profile: NavigationVLADataProfile,
    facts_by_tool: Mapping[str, dict[str, Any]],
    catalog: Iterable[ToolCapability],
) -> None:
    for facts in facts_by_tool.values():
        for issue in facts.get("blocking_issues", []) or []:
            _append_issue(profile, issue)

    if profile.topics.topic_schema == "unknown_topics":
        _append_issue(
            profile,
            {
                "type": "unknown_topic_schema",
                "message": "Cannot plan navigation workflow without image, lidar, and localization topic roles.",
            },
        )

    if profile.topics.topic_schema == "custom_topics" and not _variant_available(
        catalog, "vla_extract_and_sync", "custom_topic_mapping"
    ):
        _append_issue(
            profile,
            {
                "type": "missing_custom_topic_mapping_support",
                "message": "Custom topics require an available extract/sync custom mapping variant.",
            },
        )

    gridmap_decision = profile.stage_variants.get("gridmap_processing")
    if (
        profile.gridmap.expect_gridmap_output
        and not profile.gridmap.projection_input_gridmap_ready
        and gridmap_decision is None
    ):
        _append_issue(
            profile,
            {
                "type": "missing_gridmap_source_or_generator",
                "message": (
                    "Final outputs require grid_map, but no raw topic, existing artifact, "
                    "or available generation tool was found."
                ),
            },
        )

    for stage_kind, decision in profile.stage_variants.items():
        tool = _STAGE_TOOL_DEFAULTS.get(stage_kind, ("", ""))[0]
        if tool and not _variant_available(catalog, tool, decision.variant):
            _append_issue(
                profile,
                {
                    "type": "missing_tool_variant",
                    "message": f"{tool}/{decision.variant} is not available.",
                    "details": {"tool": tool, "variant": decision.variant},
                },
            )


def _unsupported_manipulation_plan(user_inputs: Mapping[str, Any]) -> VLAWorkflowPlan:
    date = str(user_inputs.get("date") or "unknown")
    return VLAWorkflowPlan(
        plan_id=f"vla_plan_manipulation_{date}_unsupported",
        scenario="manipulation_vla",
        status="failed",
        active_stages=[],
        skipped_stages=[
            SkippedStage(
                stage_kind="manipulation_vla",
                reason="unsupported_scenario",
                evidence=["manipulation_vla_template"],
                source="workflow_template",
            )
        ],
        approval_required=False,
        **_PLAN_REFS,
    )


def _facts_by_tool(observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_tool: dict[str, dict[str, Any]] = {}
    for observation in observations:
        tool = str(observation.get("tool") or "")
        facts = observation.get("extracted_facts")
        if not isinstance(facts, dict):
            facts = observation.get("raw_result")
        if tool and isinstance(facts, dict):
            by_tool[tool] = dict(facts)
    return by_tool


def _merged_facts(observations: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for observation in observations:
        facts = observation.get("extracted_facts") or observation.get("raw_result") or {}
        if isinstance(facts, dict):
            merged.update(facts)
    return merged


def _evidence_from_observations(observations: list[dict[str, Any]]) -> dict[str, list[str]]:
    evidence: dict[str, list[str]] = {}
    mapping = {
        "vla_inspect_raw_layout": ["dataset.raw_date_dir", "dataset.raw_work_dir", "raw_segments"],
        "vla_inspect_rosbag_metadata": ["topics.raw_topics"],
        "vla_classify_navigation_topic_schema": ["topics.topic_schema"],
        "vla_infer_sync_policy": ["sync.query_raw_dir", "sync.query_canonical_dir"],
        "vla_inspect_processing_state": ["processing_state"],
        "vla_infer_localization_policy": ["localization.source"],
        "vla_inspect_calibration_assets": ["calibration.sensor_params_dir"],
        "vla_inspect_gridmap_artifacts": [
            "gridmap.gridmap_source",
            "gridmap.expect_gridmap_output",
        ],
    }
    for observation in observations:
        obs_id = str(observation.get("observation_id") or observation.get("tool") or "")
        if not obs_id:
            continue
        for key in mapping.get(str(observation.get("tool")), []):
            evidence.setdefault(key, []).append(obs_id)
    return evidence


def _selected_segments(user_inputs: Mapping[str, Any], raw_layout: Mapping[str, Any]) -> list[str]:
    selected = user_inputs.get("selected_segments")
    if selected == "all":
        selected = None
    if isinstance(selected, str):
        return [item.strip() for item in selected.split(",") if item.strip()]
    if isinstance(selected, list) and selected:
        return [str(item) for item in selected]
    return [str(segment.get("name")) for segment in raw_layout.get("segments", [])]


def _skip_decisions(profile: NavigationVLADataProfile) -> dict[str, SkippedStage]:
    skipped: dict[str, SkippedStage] = {}
    if profile.gridmap.projection_input_gridmap_ready:
        skipped["gridmap_processing"] = SkippedStage(
            stage_kind="gridmap_processing",
            reason="grid_map_already_prepared",
            evidence=profile.evidence.get("gridmap.gridmap_source", []),
            source="previous_artifacts",
        )
    return skipped


def _catalog_by_stage(catalog: Iterable[ToolCapability]) -> dict[str, ToolCapability]:
    return {
        capability.stage_kind: capability
        for capability in catalog
        if capability.stage_kind in _STAGE_TOOL_DEFAULTS
        and capability.implementation_status == "available"
    }


def _variant_available(
    catalog: Iterable[ToolCapability],
    tool: str,
    variant_id: str,
) -> bool:
    for capability in catalog:
        if capability.tool != tool or capability.implementation_status != "available":
            continue
        return any(
            variant.id == variant_id and variant.status == "available"
            for variant in capability.variants
        )
    return False


def _append_issue(profile: NavigationVLADataProfile, issue: Mapping[str, Any]) -> None:
    issue_type = str(issue.get("type") or "")
    if issue_type and any(existing.type == issue_type for existing in profile.blocking_issues):
        return
    profile.blocking_issues.append(ProfileIssue.model_validate(dict(issue)))


def _default_sync_dir(topic_schema: str) -> str:
    if topic_schema == "go2w_current_topics":
        return "rs32_lidar_points"
    return "lidar_points"


def _localization_variant(source: str) -> str:
    if source == "ins":
        return "ins_native"
    if source == "generated_ins":
        return "indoor_cp_ins"
    return "odom_convert_resize"


def _default_effect(stage_kind: str) -> str:
    if stage_kind in {"inspect_raw_date", "check_runtime", "list_clip_segments", "validate_outputs"}:
        return "read"
    if stage_kind in {"prepare_raw_temp", "prepare_finish_dataset"}:
        return "write"
    return "execute"


def _join(root: str, child: str) -> str:
    return f"{root.rstrip('/')}/{child}" if root and child else ""


def _plan_id(user_inputs: Mapping[str, Any], profile: NavigationVLADataProfile) -> str:
    date = str(user_inputs.get("date") or profile.dataset.date or "unknown")
    return f"vla_plan_navigation_{date}_001"


def _understood_rules(scenario: str) -> list[dict[str, str]]:
    if scenario != "navigation_vla":
        return [
            {
                "id": "unsupported_scenario",
                "text": "Only navigation_vla is executable in the first workflow release.",
            }
        ]
    return [
        {
            "id": "topic_schema_from_topics",
            "text": "Topic schema decisions must be based on observed topics rather than date values.",
        },
        {
            "id": "gridmap_required",
            "text": "Navigation final outputs require grid_map; missing sources must block planning.",
        },
        {
            "id": "plan_contains_no_tool_args",
            "text": "VLAWorkflowPlan records stages, tools, variants, and skips only.",
        },
    ]


def _required_observations(scenario: str) -> list[str]:
    if scenario != "navigation_vla":
        return []
    return [
        "raw_layout",
        "rosbag_metadata",
        "topic_schema",
        "sync_policy",
        "processing_state",
        "calibration_assets",
        "localization_policy",
        "gridmap_artifacts",
        "trajectory_script_variants",
        "tool_capability_catalog",
    ]


__all__ = [
    "NAVIGATION_RULE_DOC",
    "build_navigation_data_profile",
    "build_observation",
    "build_planning_notes",
    "deterministic_plan_vla_workflow",
    "generate_navigation_workflow_plan",
]

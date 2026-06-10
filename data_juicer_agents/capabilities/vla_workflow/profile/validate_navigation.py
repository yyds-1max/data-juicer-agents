from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from data_juicer_agents.capabilities.vla_workflow.profile.navigation import (
    NavigationVLADataProfile,
    ProfileIssue,
)


_RAW_TO_CANONICAL_DIRS = {
    "lidar_points": "r32_rslidar_points",
    "rs32_lidar_points": "r32_rslidar_points",
    "grid_map": "grid_map",
}


def validate_navigation_data_profile_model(
    profile: NavigationVLADataProfile | dict[str, Any],
) -> dict[str, Any]:
    """Validate cross-field consistency for a navigation VLA data profile."""

    try:
        parsed = (
            profile
            if isinstance(profile, NavigationVLADataProfile)
            else NavigationVLADataProfile.model_validate(profile)
        )
    except ValidationError as exc:
        return {
            "ok": False,
            "errors": [
                {
                    "type": "schema_validation_failed",
                    "message": str(exc),
                    "details": {"errors": exc.errors()},
                }
            ],
            "warnings": [],
        }

    errors: list[dict[str, Any]] = []

    if parsed.scenario != "navigation_vla":
        errors.append(
            {
                "type": "invalid_scenario",
                "message": "Navigation data profiles must use scenario=navigation_vla.",
                "details": {"scenario": parsed.scenario},
            }
        )

    if not parsed.topics.required_roles_present:
        errors.append(
            {
                "type": "missing_required_roles",
                "message": "Required navigation topic roles are not all present.",
                "details": {"missing_required_roles": parsed.topics.missing_required_roles},
            }
        )
    elif parsed.topics.missing_required_roles:
        errors.append(
            {
                "type": "missing_required_roles",
                "message": "missing_required_roles must be empty for a valid profile.",
                "details": {"missing_required_roles": parsed.topics.missing_required_roles},
            }
        )

    if not _sync_query_raw_dir_is_explained(parsed):
        errors.append(
            {
                "type": "invalid_sync_query_raw_dir",
                "message": "sync.query_raw_dir is not explained by raw topics or mappings.",
                "details": {
                    "query_raw_dir": parsed.sync.query_raw_dir,
                    "query_canonical_dir": parsed.sync.query_canonical_dir,
                },
            }
        )

    if parsed.localization.source == "unknown":
        errors.append(
            {
                "type": "missing_localization_source",
                "message": "Navigation VLA processing requires odom, INS, or generated INS.",
                "details": {"source": parsed.localization.source},
            }
        )

    if parsed.localization.source == "odom":
        decision = parsed.stage_variants.get("build_noobscenes_inputs")
        if decision is None or decision.variant != "odom_convert_resize":
            errors.append(
                {
                    "type": "inconsistent_localization_variant",
                    "message": (
                        "localization.source=odom requires "
                        "build_noobscenes_inputs.variant=odom_convert_resize."
                    ),
                    "details": {
                        "source": parsed.localization.source,
                        "variant": decision.variant if decision else None,
                    },
                }
            )

    if not parsed.gridmap.expect_gridmap_output:
        errors.append(
            {
                "type": "navigation_gridmap_output_required",
                "message": "Navigation VLA final validation must expect grid_map output.",
            }
        )
    elif parsed.gridmap.gridmap_source == "unknown":
        errors.append(
            {
                "type": "missing_gridmap_source",
                "message": "gridmap_source cannot be unknown when grid_map output is required.",
            }
        )

    for issue in parsed.blocking_issues:
        errors.append(_issue_to_error(issue))

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": [issue.model_dump() for issue in parsed.warnings],
    }


def _sync_query_raw_dir_is_explained(profile: NavigationVLADataProfile) -> bool:
    query_raw_dir = profile.sync.query_raw_dir
    query_canonical_dir = profile.sync.query_canonical_dir
    raw_topic_dirs = {_topic_last_segment(topic.name) for topic in profile.topics.raw_topics}

    if query_raw_dir in raw_topic_dirs:
        return True

    if _RAW_TO_CANONICAL_DIRS.get(query_raw_dir) == query_canonical_dir:
        return True

    for topic in profile.topics.raw_topics:
        if topic.canonical_dir == query_canonical_dir:
            if topic.name and query_raw_dir == _topic_last_segment(topic.name):
                return True
            if _RAW_TO_CANONICAL_DIRS.get(query_raw_dir) == topic.canonical_dir:
                return True

    return False


def _topic_last_segment(topic_name: str) -> str:
    return topic_name.rstrip("/").rsplit("/", maxsplit=1)[-1]


def _issue_to_error(issue: ProfileIssue) -> dict[str, Any]:
    payload = issue.model_dump()
    payload.setdefault("message", "")
    return payload

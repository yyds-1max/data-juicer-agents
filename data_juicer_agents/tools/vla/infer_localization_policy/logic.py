from __future__ import annotations

from typing import Any

from data_juicer_agents.tools.vla._shared.inspection import has_role, normalize_topics


def infer_localization_policy(
    *,
    topics: list[dict[str, Any]],
    scene_mode: str = "unknown",
    requires_generated_ins: bool = False,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    normalized = normalize_topics(topics)
    if has_role(normalized, "localization_odom"):
        return _policy("odom", True, False, "odom_convert_resize", run_id, log_dir)
    if has_role(normalized, "localization_ins"):
        return _policy("ins", False, False, "ins_native", run_id, log_dir)
    if scene_mode == "in" and requires_generated_ins:
        return _policy("generated_ins", False, True, "indoor_cp_ins", run_id, log_dir)
    return {
        "ok": False,
        "source": "unknown",
        "requires_odom_convert": False,
        "requires_cp_ins": False,
        "stage_variant": {"stage": "build_noobscenes_inputs", "variant": "unknown"},
        "blocking_issues": [
            {
                "type": "missing_localization_topic",
                "message": "Navigation data needs odometry, INS, or declared generated INS.",
            }
        ],
        "run_id": run_id,
        "log_dir": log_dir,
    }


def _policy(
    source: str,
    requires_odom_convert: bool,
    requires_cp_ins: bool,
    variant: str,
    run_id: str | None,
    log_dir: str | None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "source": source,
        "canonical_output": "Ins_compatible_odom" if source == "odom" else "Ins",
        "requires_odom_convert": requires_odom_convert,
        "requires_cp_ins": requires_cp_ins,
        "stage_variant": {"stage": "build_noobscenes_inputs", "variant": variant},
        "blocking_issues": [],
        "run_id": run_id,
        "log_dir": log_dir,
    }

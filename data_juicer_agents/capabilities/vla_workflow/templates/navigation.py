from __future__ import annotations

from typing import Any

NAVIGATION_STAGE_ORDER = [
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

NAVIGATION_HUMAN_CHECKPOINTS = [
    {"stage_kind": "manual_box_annotation", "type": "gui_annotation"}
]


def get_navigation_template() -> dict[str, Any]:
    return {
        "scenario": "navigation_vla",
        "status": "available",
        "stage_order": list(NAVIGATION_STAGE_ORDER),
        "human_checkpoints": [dict(item) for item in NAVIGATION_HUMAN_CHECKPOINTS],
        "variant_source": "tool_capability_catalog",
        "skip_policy": {
            "allowed": True,
            "must_record": ["reason", "evidence"],
        },
    }


__all__ = [
    "NAVIGATION_HUMAN_CHECKPOINTS",
    "NAVIGATION_STAGE_ORDER",
    "get_navigation_template",
]

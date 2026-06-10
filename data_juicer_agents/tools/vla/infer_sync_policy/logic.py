from __future__ import annotations

from typing import Any

from data_juicer_agents.tools.vla._shared.inspection import normalize_topics, topic_last_segment


def infer_sync_policy(
    *,
    topic_schema: str,
    topics: list[dict[str, Any]],
    topic_mapping_variant: str = "",
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    if topic_schema == "u_legacy_topics":
        return _ok("lidar_points", "r32_rslidar_points", topic_schema, run_id, log_dir)
    if topic_schema == "go2w_current_topics":
        return _ok("rs32_lidar_points", "r32_rslidar_points", topic_schema, run_id, log_dir)
    if topic_schema == "custom_topics":
        for topic in normalize_topics(topics):
            if topic.get("role") == "lidar":
                return _ok(
                    topic_last_segment(topic["name"]),
                    topic.get("canonical_dir") or "r32_rslidar_points",
                    topic_schema,
                    run_id,
                    log_dir,
                )
    return {
        "ok": False,
        "topic_schema": topic_schema,
        "topic_mapping_variant": topic_mapping_variant,
        "blocking_issues": [
            {
                "type": "unknown_topic_schema",
                "message": "Cannot infer sync policy without a supported topic schema.",
            }
        ],
        "run_id": run_id,
        "log_dir": log_dir,
    }


def _ok(
    query_raw_dir: str,
    query_canonical_dir: str,
    topic_schema: str,
    run_id: str | None,
    log_dir: str | None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "topic_schema": topic_schema,
        "query_raw_dir": query_raw_dir,
        "query_canonical_dir": query_canonical_dir,
        "output_dir": "sync_data",
        "sequence_suffix": "zhigu_wuhan",
        "stage_variant": {"stage": "extract_and_sync", "variant": topic_schema},
        "blocking_issues": [],
        "run_id": run_id,
        "log_dir": log_dir,
    }

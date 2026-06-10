from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
import yaml


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "vla" / "navigation"


def topics_from_fixture(date: str) -> list[dict[str, Any]]:
    metadata_path = FIXTURE_ROOT / date / "metadata.yaml"
    payload = yaml.safe_load(metadata_path.read_text(encoding="utf-8"))
    bag_info = payload["rosbag2_bagfile_information"]

    topics = []
    for item in bag_info["topics_with_message_count"]:
        metadata = item["topic_metadata"]
        topics.append(
            {
                "name": metadata["name"],
                "type": metadata["type"],
                "message_count": item["message_count"],
            }
        )
    return topics


def classify_navigation_topic_schema(*, topics: list[dict[str, Any]], date: str | None = None) -> dict[str, Any]:
    try:
        module = import_module(
            "data_juicer_agents.tools.vla.classify_navigation_topic_schema.logic"
        )
    except ModuleNotFoundError as exc:
        raise AssertionError(
            "Expected vla_classify_navigation_topic_schema logic to exist; "
            "Task 3 should implement it."
        ) from exc

    return module.classify_navigation_topic_schema(topics=topics, date=date)


def test_navigation_fixture_20270515_is_classified_from_topics_not_date():
    result = classify_navigation_topic_schema(topics=topics_from_fixture("20270515"))

    assert result["topic_schema"] == "u_legacy_topics"
    assert result["topic_mapping_variant"] == "cam5_lidar_points_utlidar_odom"
    assert result["sync_query_candidates"][0] == "lidar_points"


def test_navigation_fixture_20270605_is_classified_from_topics_not_date():
    result = classify_navigation_topic_schema(topics=topics_from_fixture("20270605"))

    assert result["topic_schema"] == "go2w_current_topics"
    assert result["topic_mapping_variant"] == "cam4_rs32_sport_odom"
    assert result["sync_query_candidates"][0] == "rs32_lidar_points"


def test_topic_schema_does_not_depend_on_date_value():
    topics = topics_from_fixture("20270605")

    result = classify_navigation_topic_schema(topics=topics, date="20990101")

    assert result["topic_schema"] == "go2w_current_topics"

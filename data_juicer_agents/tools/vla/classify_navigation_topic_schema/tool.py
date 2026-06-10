from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ClassifyNavigationTopicSchemaInput
from .logic import classify_navigation_topic_schema


def _classify_navigation_topic_schema(
    _ctx: ToolContext, args: ClassifyNavigationTopicSchemaInput
) -> ToolResult:
    payload = classify_navigation_topic_schema(**args.model_dump())
    if payload.get("ok"):
        return ToolResult.success(summary="classified navigation topic schema", data=payload)
    return ToolResult.failure(
        summary="unknown navigation topic schema",
        error_type="unknown_topic_schema",
        data=payload,
    )


VLA_CLASSIFY_NAVIGATION_TOPIC_SCHEMA = ToolSpec(
    name="vla_classify_navigation_topic_schema",
    description="Classify navigation VLA topic schema from topic names and types.",
    input_model=ClassifyNavigationTopicSchemaInput,
    output_model=None,
    executor=_classify_navigation_topic_schema,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

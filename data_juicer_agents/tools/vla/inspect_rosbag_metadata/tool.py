from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InspectRosbagMetadataInput
from .logic import inspect_rosbag_metadata


def _inspect_rosbag_metadata(_ctx: ToolContext, args: InspectRosbagMetadataInput) -> ToolResult:
    payload = inspect_rosbag_metadata(**args.model_dump())
    if payload.get("ok"):
        return ToolResult.success(summary="parsed rosbag metadata.yaml", data=payload)
    return ToolResult.failure(
        summary="failed to parse rosbag metadata.yaml",
        error_type=str(payload.get("error_type", "metadata_parse_failed")),
        error_message=str(payload.get("error_message", "")),
        data=payload,
    )


VLA_INSPECT_ROSBAG_METADATA = ToolSpec(
    name="vla_inspect_rosbag_metadata",
    description="Parse ROS2 rosbag metadata.yaml without reading db3 payloads.",
    input_model=InspectRosbagMetadataInput,
    output_model=None,
    executor=_inspect_rosbag_metadata,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

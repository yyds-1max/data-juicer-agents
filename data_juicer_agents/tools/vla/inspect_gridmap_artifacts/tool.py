from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InspectGridmapArtifactsInput
from .logic import inspect_gridmap_artifacts


def _inspect_gridmap_artifacts(_ctx: ToolContext, args: InspectGridmapArtifactsInput) -> ToolResult:
    return ToolResult.success(
        summary="inspected navigation grid_map artifact facts",
        data=inspect_gridmap_artifacts(**args.model_dump()),
    )


VLA_INSPECT_GRIDMAP_ARTIFACTS = ToolSpec(
    name="vla_inspect_gridmap_artifacts",
    description="Inspect raw topic and filesystem facts about grid_map availability.",
    input_model=InspectGridmapArtifactsInput,
    output_model=None,
    executor=_inspect_gridmap_artifacts,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

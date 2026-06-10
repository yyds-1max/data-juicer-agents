from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InspectProcessingStateInput
from .logic import inspect_processing_state


def _inspect_processing_state(_ctx: ToolContext, args: InspectProcessingStateInput) -> ToolResult:
    return ToolResult.success(
        summary="inspected VLA processing state",
        data=inspect_processing_state(**args.model_dump()),
    )


VLA_INSPECT_PROCESSING_STATE = ToolSpec(
    name="vla_inspect_processing_state",
    description="Inspect existing clip, finish temp, annotation, tracking, projection, and final artifacts.",
    input_model=InspectProcessingStateInput,
    output_model=None,
    executor=_inspect_processing_state,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

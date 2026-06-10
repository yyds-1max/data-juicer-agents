from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InspectDataToolboxVariantsInput
from .logic import inspect_datatoolbox_variants


def _inspect_datatoolbox_variants(
    _ctx: ToolContext, args: InspectDataToolboxVariantsInput
) -> ToolResult:
    return ToolResult.success(
        summary="inspected DataToolbox script variants",
        data=inspect_datatoolbox_variants(**args.model_dump()),
    )


VLA_INSPECT_DATATOOLBOX_VARIANTS = ToolSpec(
    name="vla_inspect_datatoolbox_variants",
    description="Inspect read-only DataToolbox script variant support for navigation topic schemas.",
    input_model=InspectDataToolboxVariantsInput,
    output_model=None,
    executor=_inspect_datatoolbox_variants,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

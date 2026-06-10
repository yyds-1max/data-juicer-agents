from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InspectRawLayoutInput
from .logic import inspect_raw_layout


def _inspect_raw_layout(_ctx: ToolContext, args: InspectRawLayoutInput) -> ToolResult:
    payload = inspect_raw_layout(**args.model_dump())
    if payload.get("ok"):
        return ToolResult.success(summary="inspected raw VLA layout", data=payload)
    return ToolResult.failure(
        summary="raw date directory is missing",
        error_type=str(payload.get("error_type", "missing_raw_date")),
        data=payload,
    )


VLA_INSPECT_RAW_LAYOUT = ToolSpec(
    name="vla_inspect_raw_layout",
    description="Inspect raw VLA date and segment directory layout without reading db3 files.",
    input_model=InspectRawLayoutInput,
    output_model=None,
    executor=_inspect_raw_layout,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

from __future__ import annotations

from data_juicer_agents.capabilities.vla_workflow.catalog.service import (
    list_tool_capabilities,
)
from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import ListToolCapabilityCatalogInput, ListToolCapabilityCatalogOutput


def _list_tool_capability_catalog(
    ctx: ToolContext,
    args: ListToolCapabilityCatalogInput,
) -> ToolResult:
    del ctx
    capabilities = list_tool_capabilities(
        scenario=args.scenario,
        stage_kind=args.stage_kind,
        tool=args.tool,
    )
    return ToolResult.success(
        summary=f"listed {len(capabilities)} VLA tool capabilities",
        data={
            "ok": True,
            "filters": args.model_dump(exclude_none=True),
            "capabilities": [
                capability.model_dump(mode="json") for capability in capabilities
            ],
        },
    )


VLA_LIST_TOOL_CAPABILITY_CATALOG = ToolSpec(
    name="vla_list_tool_capability_catalog",
    description=(
        "List VLA workflow tool capability metadata and stage variants. "
        "Executable plans may only use capabilities whose implementation_status "
        "and selected variant status are both available."
    ),
    input_model=ListToolCapabilityCatalogInput,
    output_model=ListToolCapabilityCatalogOutput,
    executor=_list_tool_capability_catalog,
    tags=("vla", "read"),
    effects="read",
    confirmation="none",
)


__all__ = ["VLA_LIST_TOOL_CAPABILITY_CATALOG"]

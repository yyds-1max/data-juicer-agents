from __future__ import annotations

from collections.abc import Iterable

from data_juicer_agents.core.tool import ToolSpec, list_tool_specs

from .model import ToolCapability, ToolVariant
from .navigation import NAVIGATION_TOOL_CAPABILITIES


def _copy_variant_with_status(
    variant: ToolVariant,
    *,
    status: str,
) -> ToolVariant:
    return variant.model_copy(update={"status": status}, deep=True)


def _copy_capability_with_placeholder_status(
    capability: ToolCapability,
) -> ToolCapability:
    return capability.model_copy(
        update={
            "implementation_status": "placeholder",
            "variants": [
                _copy_variant_with_status(variant, status="placeholder")
                for variant in capability.variants
            ],
        },
        deep=True,
    )


def _registered_vla_tool_specs() -> dict[str, ToolSpec]:
    return {spec.name: spec for spec in list_tool_specs(tags=["vla"])}


def apply_tool_registry_status(
    capabilities: Iterable[ToolCapability],
    *,
    registered_tools: set[str] | None = None,
    registered_specs: dict[str, ToolSpec] | None = None,
) -> list[ToolCapability]:
    """Merge declared VLA capability metadata with real ToolSpec registration."""

    if registered_tools is None:
        if registered_specs is None:
            registered_specs = _registered_vla_tool_specs()
        registered_tools = set(registered_specs)

    merged: list[ToolCapability] = []
    for capability in capabilities:
        if capability.tool not in registered_tools:
            merged.append(_copy_capability_with_placeholder_status(capability))
            continue

        spec = (registered_specs or {}).get(capability.tool)
        if spec is None:
            merged.append(capability.model_copy(deep=True))
            continue

        merged.append(
            capability.model_copy(
                update={"effects": spec.effects},
                deep=True,
            )
        )
    return merged


def list_tool_capabilities(
    *,
    scenario: str | None = None,
    stage_kind: str | None = None,
    tool: str | None = None,
) -> list[ToolCapability]:
    catalog = apply_tool_registry_status(NAVIGATION_TOOL_CAPABILITIES)

    if scenario:
        catalog = [item for item in catalog if item.scenario == scenario]
    if stage_kind:
        catalog = [item for item in catalog if item.stage_kind == stage_kind]
    if tool:
        catalog = [item for item in catalog if item.tool == tool]
    return catalog


def find_tool_capability(
    catalog: Iterable[ToolCapability],
    tool: str,
) -> ToolCapability:
    for capability in catalog:
        if capability.tool == tool:
            return capability
    raise KeyError(f"tool capability not found: {tool}")


__all__ = [
    "apply_tool_registry_status",
    "find_tool_capability",
    "list_tool_capabilities",
]

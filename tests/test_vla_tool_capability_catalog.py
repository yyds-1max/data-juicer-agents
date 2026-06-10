from __future__ import annotations

from data_juicer_agents.capabilities.vla_workflow.catalog.model import (
    ToolCapability,
    ToolVariant,
)
from data_juicer_agents.capabilities.vla_workflow.catalog.service import (
    apply_tool_registry_status,
    find_tool_capability,
    list_tool_capabilities,
)
from data_juicer_agents.core.tool import ToolContext, ToolSpec, list_tool_specs
from data_juicer_agents.tools.vla.list_tool_capability_catalog.tool import (
    VLA_LIST_TOOL_CAPABILITY_CATALOG,
)


def _variant(capability: ToolCapability, variant_id: str) -> ToolVariant:
    for variant in capability.variants:
        if variant.id == variant_id:
            return variant
    raise AssertionError(f"variant not found: {capability.tool}/{variant_id}")


def test_extract_sync_topic_variants_expose_current_implementation_status():
    capability = find_tool_capability(
        list_tool_capabilities(scenario="navigation_vla"),
        "vla_extract_and_sync",
    )

    assert capability.implementation_status == "available"
    assert _variant(capability, "u_legacy_topics").status == "available"
    assert _variant(capability, "go2w_current_topics").status == "available"
    assert _variant(capability, "custom_topic_mapping").status != "available"


def test_extract_sync_current_variant_is_available_after_implementation():
    catalog = list_tool_capabilities(scenario="navigation_vla")
    capability = find_tool_capability(catalog, "vla_extract_and_sync")

    assert _variant(capability, "go2w_current_topics").status == "available"


def test_gridmap_projection_and_validation_variants_are_available():
    catalog = list_tool_capabilities(scenario="navigation_vla")

    gridmap = find_tool_capability(catalog, "vla_prepare_gridmap")
    assert _variant(gridmap, "copy_existing_artifact").status == "available"
    assert _variant(gridmap, "pointcloud_to_gridmap").status == "available"

    projection = find_tool_capability(catalog, "vla_run_projection_and_trajectory")
    assert _variant(projection, "cjl_with_gridmap").status == "available"
    assert _variant(projection, "cjl_0525_with_gridmap").status == "available"

    validation = find_tool_capability(catalog, "vla_validate_outputs")
    assert _variant(validation, "expect_gridmap").status == "available"


def test_prepare_finish_dataset_binds_explicit_sensor_params_from_profile():
    capability = find_tool_capability(
        list_tool_capabilities(scenario="navigation_vla"),
        "vla_prepare_finish_dataset",
    )

    assert (
        _variant(capability, "explicit_sensor_params").arg_bindings[
            "sensor_params_dir"
        ]
        == "calibration.sensor_params_dir"
    )


def test_missing_declared_tool_is_downgraded_to_placeholder():
    capability = ToolCapability(
        tool="vla_missing_future_tool",
        scenario="navigation_vla",
        stage_kind="future_stage",
        effects="execute",
        implementation_status="available",
        supports_dry_run=True,
        plan_agent_allowed=False,
        executor_agent_allowed=True,
        variants=[ToolVariant(id="default", status="available")],
    )
    merged = apply_tool_registry_status([capability], registered_tools=set())

    assert merged[0].implementation_status == "placeholder"
    assert merged[0].variants[0].status == "placeholder"


def test_all_execute_tools_are_executor_only():
    execute_capabilities = [
        capability
        for capability in list_tool_capabilities(scenario="navigation_vla")
        if capability.effects == "execute"
    ]

    assert execute_capabilities
    assert all(not capability.plan_agent_allowed for capability in execute_capabilities)
    assert all(capability.executor_agent_allowed for capability in execute_capabilities)


def test_catalog_can_be_filtered_by_stage_kind_and_tool():
    catalog = list_tool_capabilities(
        scenario="navigation_vla",
        stage_kind="gridmap_processing",
        tool="vla_prepare_gridmap",
    )

    assert [capability.tool for capability in catalog] == ["vla_prepare_gridmap"]
    assert catalog[0].stage_kind == "gridmap_processing"


def test_list_tool_capability_catalog_tool_returns_filtered_payload():
    result = VLA_LIST_TOOL_CAPABILITY_CATALOG.execute(
        ToolContext(),
        {"scenario": "navigation_vla", "tool": "vla_prepare_gridmap"},
    )

    assert result.ok
    payload = result.to_payload()
    assert payload["ok"] is True
    assert [item["tool"] for item in payload["capabilities"]] == [
        "vla_prepare_gridmap"
    ]
    assert payload["capabilities"][0]["variants"][0]["status"] == "available"


def test_list_catalog_tool_is_read_only_vla_tool_spec():
    spec = VLA_LIST_TOOL_CAPABILITY_CATALOG

    assert isinstance(spec, ToolSpec)
    assert spec.name == "vla_list_tool_capability_catalog"
    assert spec.effects == "read"
    assert spec.confirmation == "none"
    assert {"vla", "read"}.issubset(set(spec.tags))


def test_list_catalog_tool_is_auto_discovered():
    names = {spec.name for spec in list_tool_specs(tags=["vla"])}

    assert "vla_list_tool_capability_catalog" in names

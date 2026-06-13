from __future__ import annotations

from data_juicer_agents.capabilities.vla_workflow.profile.validate_navigation import (
    validate_navigation_data_profile_model,
)
from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import (
    ValidateNavigationDataProfileInput,
    ValidateNavigationDataProfileOutput,
)


def _validate_navigation_data_profile(
    ctx: ToolContext,
    args: ValidateNavigationDataProfileInput,
) -> ToolResult:
    del ctx
    validation = validate_navigation_data_profile_model(args.profile)
    payload = {
        "ok": bool(validation["ok"]),
        "errors": list(validation["errors"]),
        "warnings": list(validation["warnings"]),
    }
    if payload["ok"]:
        return ToolResult.success(
            summary="navigation VLA data profile is valid",
            data=payload,
        )
    return ToolResult.failure(
        summary="navigation VLA data profile is invalid",
        error_type="navigation_data_profile_invalid",
        data=payload,
    )


VLA_VALIDATE_NAVIGATION_DATA_PROFILE = ToolSpec(
    name="vla_validate_navigation_data_profile",
    description=(
        "Validate a NavigationVLADataProfile draft for schema and navigation "
        "cross-field consistency. Use this read-only tool before treating a "
        "profile draft as an executable planning input."
    ),
    input_model=ValidateNavigationDataProfileInput,
    output_model=ValidateNavigationDataProfileOutput,
    executor=_validate_navigation_data_profile,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)


__all__ = ["VLA_VALIDATE_NAVIGATION_DATA_PROFILE"]

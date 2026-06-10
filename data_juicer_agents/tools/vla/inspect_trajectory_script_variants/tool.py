from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InspectTrajectoryScriptVariantsInput
from .logic import inspect_trajectory_script_variants


def _inspect_trajectory_script_variants(
    _ctx: ToolContext, args: InspectTrajectoryScriptVariantsInput
) -> ToolResult:
    return ToolResult.success(
        summary="inspected trajectory script variants",
        data=inspect_trajectory_script_variants(**args.model_dump()),
    )


VLA_INSPECT_TRAJECTORY_SCRIPT_VARIANTS = ToolSpec(
    name="vla_inspect_trajectory_script_variants",
    description="Inspect projection, trajectory, move, and gridmap helper script availability.",
    input_model=InspectTrajectoryScriptVariantsInput,
    output_model=None,
    executor=_inspect_trajectory_script_variants,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

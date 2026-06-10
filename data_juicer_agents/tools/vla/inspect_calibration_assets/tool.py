from __future__ import annotations

from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec

from .input import InspectCalibrationAssetsInput
from .logic import inspect_calibration_assets


def _inspect_calibration_assets(_ctx: ToolContext, args: InspectCalibrationAssetsInput) -> ToolResult:
    payload = inspect_calibration_assets(**args.model_dump())
    if payload.get("ok"):
        return ToolResult.success(summary="inspected navigation calibration assets", data=payload)
    return ToolResult.failure(
        summary="recommended navigation calibration assets are missing or incomplete",
        error_type="missing_calibration_assets",
        data=payload,
    )


VLA_INSPECT_CALIBRATION_ASSETS = ToolSpec(
    name="vla_inspect_calibration_assets",
    description="Inspect NoobScenes sensor calibration assets for navigation topic schemas.",
    input_model=InspectCalibrationAssetsInput,
    output_model=None,
    executor=_inspect_calibration_assets,
    tags=("vla", "read", "planning"),
    effects="read",
    confirmation="none",
)

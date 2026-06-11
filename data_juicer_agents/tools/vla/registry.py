from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec
from data_juicer_agents.tools.vla.build_noobscenes_inputs import (
    VLA_BUILD_NOOBSCENES_INPUTS,
)
from data_juicer_agents.tools.vla.check_runtime import VLA_CHECK_RUNTIME
from data_juicer_agents.tools.vla.extract_and_sync import VLA_EXTRACT_AND_SYNC
from data_juicer_agents.tools.vla.classify_navigation_topic_schema import (
    VLA_CLASSIFY_NAVIGATION_TOPIC_SCHEMA,
)
from data_juicer_agents.tools.vla.infer_localization_policy import (
    VLA_INFER_LOCALIZATION_POLICY,
)
from data_juicer_agents.tools.vla.infer_sync_policy import VLA_INFER_SYNC_POLICY
from data_juicer_agents.tools.vla.inspect_calibration_assets import (
    VLA_INSPECT_CALIBRATION_ASSETS,
)
from data_juicer_agents.tools.vla.inspect_datatoolbox_variants import (
    VLA_INSPECT_DATATOOLBOX_VARIANTS,
)
from data_juicer_agents.tools.vla.inspect_gridmap_artifacts import (
    VLA_INSPECT_GRIDMAP_ARTIFACTS,
)
from data_juicer_agents.tools.vla.inspect_processing_state import (
    VLA_INSPECT_PROCESSING_STATE,
)
from data_juicer_agents.tools.vla.inspect_raw_date import VLA_INSPECT_RAW_DATE
from data_juicer_agents.tools.vla.inspect_raw_layout import VLA_INSPECT_RAW_LAYOUT
from data_juicer_agents.tools.vla.inspect_rosbag_metadata import (
    VLA_INSPECT_ROSBAG_METADATA,
)
from data_juicer_agents.tools.vla.inspect_trajectory_script_variants import (
    VLA_INSPECT_TRAJECTORY_SCRIPT_VARIANTS,
)
from data_juicer_agents.tools.vla.list_clip_segments import VLA_LIST_CLIP_SEGMENTS
from data_juicer_agents.tools.vla.list_tool_capability_catalog import (
    VLA_LIST_TOOL_CAPABILITY_CATALOG,
)
from data_juicer_agents.tools.vla.prepare_finish_dataset import (
    VLA_PREPARE_FINISH_DATASET,
)
from data_juicer_agents.tools.vla.prepare_gridmap import VLA_PREPARE_GRIDMAP
from data_juicer_agents.tools.vla.prepare_raw_temp import VLA_PREPARE_RAW_TEMP
from data_juicer_agents.tools.vla.run_manual_box_annotation import (
    VLA_RUN_MANUAL_BOX_ANNOTATION,
)
from data_juicer_agents.tools.vla.run_workflow import VLA_RUN_WORKFLOW
from data_juicer_agents.tools.vla.run_projection_and_trajectory import (
    VLA_RUN_PROJECTION_AND_TRAJECTORY,
)
from data_juicer_agents.tools.vla.run_tracking import VLA_RUN_TRACKING
from data_juicer_agents.tools.vla.validate_outputs import VLA_VALIDATE_OUTPUTS


TOOL_SPECS: List[ToolSpec] = [
    VLA_RUN_WORKFLOW,
    VLA_CHECK_RUNTIME,
    VLA_INSPECT_RAW_DATE,
    VLA_INSPECT_RAW_LAYOUT,
    VLA_INSPECT_ROSBAG_METADATA,
    VLA_CLASSIFY_NAVIGATION_TOPIC_SCHEMA,
    VLA_INFER_SYNC_POLICY,
    VLA_INSPECT_DATATOOLBOX_VARIANTS,
    VLA_INSPECT_PROCESSING_STATE,
    VLA_INSPECT_CALIBRATION_ASSETS,
    VLA_INFER_LOCALIZATION_POLICY,
    VLA_INSPECT_GRIDMAP_ARTIFACTS,
    VLA_INSPECT_TRAJECTORY_SCRIPT_VARIANTS,
    VLA_LIST_TOOL_CAPABILITY_CATALOG,
    VLA_PREPARE_RAW_TEMP,
    VLA_EXTRACT_AND_SYNC,
    VLA_LIST_CLIP_SEGMENTS,
    VLA_PREPARE_FINISH_DATASET,
    VLA_BUILD_NOOBSCENES_INPUTS,
    VLA_RUN_MANUAL_BOX_ANNOTATION,
    VLA_RUN_TRACKING,
    VLA_PREPARE_GRIDMAP,
    VLA_RUN_PROJECTION_AND_TRAJECTORY,
    VLA_VALIDATE_OUTPUTS,
]


__all__ = ["TOOL_SPECS"]

from __future__ import annotations

from typing import List

from data_juicer_agents.core.tool import ToolSpec
from data_juicer_agents.tools.vla.build_noobscenes_inputs import (
    VLA_BUILD_NOOBSCENES_INPUTS,
)
from data_juicer_agents.tools.vla.check_runtime import VLA_CHECK_RUNTIME
from data_juicer_agents.tools.vla.extract_and_sync import VLA_EXTRACT_AND_SYNC
from data_juicer_agents.tools.vla.inspect_raw_date import VLA_INSPECT_RAW_DATE
from data_juicer_agents.tools.vla.list_clip_segments import VLA_LIST_CLIP_SEGMENTS
from data_juicer_agents.tools.vla.prepare_finish_dataset import (
    VLA_PREPARE_FINISH_DATASET,
)
from data_juicer_agents.tools.vla.prepare_gridmap import VLA_PREPARE_GRIDMAP
from data_juicer_agents.tools.vla.prepare_raw_temp import VLA_PREPARE_RAW_TEMP
from data_juicer_agents.tools.vla.run_manual_box_annotation import (
    VLA_RUN_MANUAL_BOX_ANNOTATION,
)
from data_juicer_agents.tools.vla.run_projection_and_trajectory import (
    VLA_RUN_PROJECTION_AND_TRAJECTORY,
)
from data_juicer_agents.tools.vla.run_tracking import VLA_RUN_TRACKING
from data_juicer_agents.tools.vla.validate_outputs import VLA_VALIDATE_OUTPUTS


TOOL_SPECS: List[ToolSpec] = [
    VLA_CHECK_RUNTIME,
    VLA_INSPECT_RAW_DATE,
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

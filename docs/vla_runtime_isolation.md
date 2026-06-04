# VLA Runtime Isolation

The Agent runtime uses Python 3.10 or newer. It should install only the
Data-Juicer Agents dependencies needed for orchestration.

The data-processing runtime uses the server's legacy Python 3.8 environment
with ROS2, CUDA, OpenCV, Open3D, PCL, GUI libraries, and compiled tracking
binaries.

Configure the data runtime before running VLA tools:

```bash
export AGENT_DATA_ENV_SETUP=/media/heying/hy_data2/GT_dog/env/setup_data_runtime.sh
export AGENT_DATA_PYTHON=/usr/bin/python3.8
```

Verify the boundary:

```bash
python --version
bash -lc 'source "$AGENT_DATA_ENV_SETUP" && "$AGENT_DATA_PYTHON" --version'
```

Expected:

- Agent Python: 3.10 or newer
- Data Python: 3.8

If the second command reports Python 3.10, set `AGENT_DATA_PYTHON` to an
absolute Python 3.8 executable.

The VLA tools must launch legacy scripts and binaries through subprocess
wrappers. Do not import ROS2, CUDA, OpenCV, Open3D, PCL, GUI, or legacy
data-processing modules into the Agent Python process.

Typical server environment variables:

```bash
export VLA_RAW_ROOT=/media/heying/hy_data1/VLADatasets/raw_data
export VLA_CLIP_ROOT=/media/heying/hy_data1/VLADatasets/clip_data
export VLA_FINISH_ROOT=/media/heying/hy_data1/VLADatasets/finish_data
export VLA_DATA_TOOLBOX_SRC=/media/heying/hy_data2/GT_dog/modules_ros2/DataToolbox/src
export VLA_TRAJECTORY_ROOT=/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01
export VLA_GT_DOG_ROOT=/media/heying/hy_data2/GT_dog
```

For local WSL development, missing server paths are expected. Use dry-run
tool calls and unit tests to validate command shape and path planning, then
upload the repository to the server for ROS2, GUI annotation, tracking, and
projection integration runs.

Recommended preflight:

```bash
python -m pytest \
  tests/test_vla_runtime_helpers.py \
  tests/test_vla_logging.py \
  tests/test_vla_raw_tools.py \
  tests/test_vla_extract_sync_tools.py \
  tests/test_vla_finish_tools.py \
  tests/test_vla_annotation_tracking_tools.py \
  tests/test_vla_projection_validation_tools.py \
  tests/test_vla_registry_session.py \
  -v
```

Before running the full data flow, call `vla_check_runtime` with the configured
`AGENT_DATA_ENV_SETUP` and `AGENT_DATA_PYTHON`. A failed runtime check should
be fixed before running `vla_extract_and_sync`, `vla_run_manual_box_annotation`,
`vla_run_tracking`, or `vla_run_projection_and_trajectory`.

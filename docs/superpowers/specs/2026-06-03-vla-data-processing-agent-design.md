# VLA Data Processing Agent Design

## Goal

Build a VLA data processing agent on top of the existing Data-Juicer Agents framework. The agent should orchestrate the user's current ROS2 bag, synchronization, odometry, tracking, point projection, and trajectory workflow while preserving the existing manual annotation step in `gen_box.py`.

The implementation should run primarily in local WSL during development, then be uploaded to the server for full execution. Missing server paths in the local checkout are expected and should be handled with dry-run and validation modes.

## Existing Flow

The current pipeline is:

1. `VLADatasets/raw_data/prepare.sh`
   - Input: processing date and selected raw db3 folders.
   - Output: symlinks under `raw_data/${DATE}_temp` and a date folder under `clip_data/${DATE}`.

2. `run_U.sh`
   - Input: date.
   - Reads `raw_data/${DATE}_temp`.
   - Runs ROS2 extraction with `1_extract_data_from_bag_multi_process_ros2_U.py`.
   - Runs timestamp synchronization with `2_sync_data_multi_process_U.py`.
   - Output: `clip_data/${DATE}/${segment}/sync_data`.

3. `run_odom.sh`
   - Input: date, selected clip segments, and indoor/outdoor mode.
   - Builds `finish_data/${DATE}_temp` and final `finish_data/${DATE}`.
   - Runs metadata generation, odom conversion, image resizing, NoobScenes generation, video generation, manual box annotation, tracking, point projection, world-coordinate conversion, speed/direction calculation, trajectory generation, and result movement.

## Recommended Architecture

Add a new tool group:

```text
data_juicer_agents/tools/vla/
```

This group should expose structured tools via the existing `ToolSpec` registry pattern. Because `data_juicer_agents/core/tool/catalog.py` automatically discovers tool groups with `registry.py`, these tools will be available to both `djx tool` and `dj-agents` ReAct sessions.

The VLA agent should reuse the current `DJSessionAgent` and AgentScope `ReActAgent`. We should not introduce a separate agent framework.

## Runtime Isolation

The Agent runtime and data-processing runtime must be isolated.

The Agent runtime may run on Python 3.10 or newer and should only import lightweight orchestration dependencies such as AgentScope, Pydantic, CLI/session code, logging, and test helpers. It must not import ROS2, OpenCV, Open3D, PCL, CUDA-specific packages, GUI packages, or the legacy data-processing modules directly.

The data-processing runtime is the server's legacy Python 3.8 environment plus ROS2, CUDA, OpenCV, Open3D, PCL, compiled C++ binaries, Tkinter/OpenCV GUI support, and project-specific shared libraries. All legacy scripts and binaries should run through subprocesses.

Use the same isolation pattern as the prior preprocessing agent:

```bash
export AGENT_DATA_ENV_SETUP=/media/heying/hy_data2/GT_dog/env/setup_data_runtime.sh
export AGENT_DATA_PYTHON=/usr/bin/python3.8
```

`AGENT_DATA_ENV_SETUP` points to a server-side shell setup script that sources ROS/CUDA/library paths and may activate the legacy Python environment. `AGENT_DATA_PYTHON` points to the Python executable for legacy scripts. Prefer an absolute Python 3.8 path on the server because the Agent's conda/venv may otherwise make plain `python3` resolve to Python 3.10.

Python data commands should be wrapped so `$AGENT_DATA_PYTHON` is resolved after the setup script is sourced:

```bash
bash -lc 'export AGENT_DATA_PYTHON=/usr/bin/python3.8 && source "$AGENT_DATA_ENV_SETUP" && exec "$AGENT_DATA_PYTHON" script.py ...'
```

Binary commands, such as `1_onnx_tam/bin/main`, should use the same setup wrapper but execute the binary directly:

```bash
bash -lc 'source "$AGENT_DATA_ENV_SETUP" && exec ./bin/main'
```

The implementation should provide shared helpers:

- `data_runtime_command(argv)`: wraps any executable in the data runtime setup when configured.
- `python_data_command(script_path, args)`: wraps Python scripts with `AGENT_DATA_PYTHON`.
- `run_u_python_command(...)`: additionally sources the ROS2 setup scripts and preserves the `LD_LIBRARY_PATH` behavior from `run_U.sh`.

The VLA tools should log both the wrapped command and the resolved runtime check. A precheck tool should verify:

- Agent Python version is 3.10 or newer.
- Data runtime Python is 3.8 when `AGENT_DATA_ENV_SETUP` and `AGENT_DATA_PYTHON` are configured.
- ROS setup scripts and required shared library directories exist on the server.

Local dry-run tests should validate command shape without requiring Python 3.8, ROS, CUDA, or GUI packages.

## Tools

### `vla_check_runtime`

Verifies Agent/runtime isolation before heavy execution.

Inputs:
- `data_env_setup`
- `data_python`
- `expected_data_python_major_minor`, default `3.8`
- `dry_run`

Outputs:
- Agent Python version
- data runtime Python version
- setup script existence
- key environment values after setup
- warnings if `python3` would resolve to the Agent runtime

### `vla_inspect_raw_date`

Lists raw db3 segment folders for a date.

Inputs:
- `date`
- `raw_root`

Outputs:
- available segment names
- existence checks
- warnings for missing metadata or db3 files

### `vla_prepare_raw_temp`

Structured replacement for `prepare.sh`.

Inputs:
- `date`
- `selected_segments`
- `raw_root`
- `clip_root`
- `owner` optional, for server-side chown
- `dry_run`

Outputs:
- created or planned symlink paths
- clip date directory path
- skipped segments

This tool should require confirmation because it creates directories and symlinks.

### `vla_extract_and_sync`

Structured replacement for the core of `run_U.sh`.

Inputs:
- `date`
- `raw_root`
- `clip_root`
- `data_toolbox_src`
- `data_env_setup`
- `data_python`
- `processes_num`
- `query_dir`, default `lidar_points`
- `sync_output_dir`, default `sync_data`
- `sequence_suffix`, default `zhigu_wuhan`
- ROS setup scripts and extra environment variables
- `dry_run`

Outputs:
- per-segment extraction command result
- per-segment synchronization command result
- generated `clip_data` paths

This tool should execute one segment at a time and return partial progress instead of hiding all work inside one shell script.

### `vla_list_clip_segments`

Lists clip segments under `clip_data/${DATE}`.

Inputs:
- `date`
- `clip_root`

Outputs:
- available segment folders
- whether each segment contains `sync_data`

### `vla_prepare_finish_dataset`

Structured replacement for the non-interactive preparation part of `run_odom.sh`.

Inputs:
- `date`
- `selected_segments`
- `scene_mode`, one of `in` or `out`
- `clip_root`
- `finish_root`
- `trajectory_root`
- `sensor_params_dir`
- `dry_run`

Outputs:
- `save_path`
- `save_path_temp`
- copied clip paths
- missing subdirectories

### `vla_build_noobscenes_inputs`

Runs the deterministic preprocessing steps before manual annotation:

- create empty annotation JSON with `0_creat_box.py`
- convert odom with `1_odom_convert.py`
- resize images with `2_resize.py`
- create `v1.0-trainval` via `main_smart_odom.py`
- copy `maps/map.png`
- generate `dog.mp4` via `img2video.py`

Inputs:
- `save_path_temp`
- `trajectory_root`
- `data_env_setup`
- `data_python`
- optional `dataset_version`
- `dry_run`

Outputs:
- generated metadata paths
- video paths
- warnings for missing clips or images

### `vla_run_manual_box_annotation`

Runs `gen_box.py --dataset_root <save_path_temp>` as a human-in-the-loop checkpoint.

Behavior:
- Launches the existing GUI/OpenCV/Tkinter workflow unchanged.
- Blocks until the user closes/completes the annotation script.
- Does not simulate clicks or automate annotation.
- After the script exits, scans each clip for generated `master_*.yaml` and `other*.yaml`.

Inputs:
- `save_path_temp`
- `trajectory_root`
- `data_env_setup`
- `data_python`
- `expected_clips`
- `timeout`, optional

Outputs:
- generated yaml files per clip
- clips without yaml files
- process exit code

If no yaml files are produced for a selected clip, the tool returns `ok=false` with a clear checkpoint message so the ReAct agent can ask the user whether to retry, skip, or stop.

This tool requires a GUI-capable environment such as WSLg or X11 forwarding on the server.

### `vla_run_tracking`

Runs the ONNX tracking stage after YAML files exist.

Inputs:
- `save_path_temp`
- `trajectory_root`
- `data_env_setup`
- `cuda_env`
- `timeout`
- `dry_run`

Outputs:
- tracking image directories
- `img_<identity>_<colors>.txt` files
- failed yaml files

### `vla_run_projection_and_trajectory`

Runs the remaining deterministic post-tracking steps:

- `NuscenesAanlysis_smart_pts_project/main.py`
- `2_pt_project/0_img2world.py`
- `2_pt_project/4_speed_direction_odom.py`
- optional `cp_gridmap.py` only when configured or detected
- `2_pt_project/2_othermethod_cjl.py`
- `2_pt_project/3_move_dir.py`

Inputs:
- `save_path`
- `save_path_temp`
- `trajectory_root`
- `data_env_setup`
- `data_python`
- `use_gridmap`
- `dry_run`

Outputs:
- generated projection files
- world-coordinate files
- speed/direction outputs
- trajectory outputs
- moved final result paths

### `vla_validate_outputs`

Checks required outputs at each stage.

Inputs:
- `date`
- `clip_root`
- `finish_root`
- `selected_segments`
- validation level: `clip`, `finish`, or `full`

Outputs:
- present/missing files and directories
- per-clip readiness summary
- suggested next action

## ReAct Orchestration

Add VLA-specific instructions to the session prompt:

When the user asks to process VLA / dog / odom / ROS2 db3 data, follow this default chain:

```text
vla_inspect_raw_date
-> vla_check_runtime
-> vla_prepare_raw_temp
-> vla_extract_and_sync
-> vla_list_clip_segments
-> vla_prepare_finish_dataset
-> vla_build_noobscenes_inputs
-> vla_run_manual_box_annotation
-> vla_run_tracking
-> vla_run_projection_and_trajectory
-> vla_validate_outputs
```

The agent should ask for missing explicit choices:

- date
- selected raw db3 folders, or all
- selected clip segments, or all
- `in` or `out`
- whether to continue after the manual annotation checkpoint if some clips have no YAML

The agent should not run destructive or long-running stages without confirmation.

For all VLA Python scripts, the agent should call tools that use the isolated data runtime instead of running `python3` directly. For tracking binaries, the agent should still source the data runtime setup so CUDA and shared library paths are consistent with the server environment.

## Logging

The system should persist logs for every agent-run pipeline. Logging should include both human-readable logs and structured JSONL events.

Recommended log root:

```text
<working_dir>/vla_runs/<date>/<run_id>/
```

Files:

- `run.json`: immutable run metadata, including date, selected segments, roots, scene mode, model/session settings, start time, and command-line options.
- `events.jsonl`: structured event stream. Each line records `timestamp`, `stage`, `event_type`, `ok`, `message`, paths, command, return code, elapsed seconds, and relevant counts.
- `commands.log`: shell commands executed, with environment summaries but without secret values.
- `stdout.log`: captured stdout by stage.
- `stderr.log`: captured stderr by stage.
- `summary.json`: final status, completed stages, failed stage, missing outputs, and next recommended action.

Every VLA tool should accept an optional `run_id` and `log_dir`. If absent, the runtime creates them. The ReAct session should surface the log directory in the final reply for each run.

The logs should record the runtime boundary explicitly:

- Agent Python executable and version.
- Data runtime setup script path.
- Data Python executable configured before setup.
- Data Python version observed after setup.
- Whether a command ran as `python_data_command`, `data_runtime_command`, or `run_u_python_command`.

The manual annotation checkpoint should log:

- command start
- GUI checkpoint start
- process exit
- YAML files discovered after exit
- missing YAML files by clip

The log format should be useful on the server: copying only the run log directory should be enough to debug the failed stage without rerunning the full pipeline.

## Error Handling

The tools should return structured failures instead of only printing shell output.

Examples:

- Missing raw date folder: fail before creating temp folders.
- Data runtime resolves to Python 3.10 instead of Python 3.8: fail before running legacy scripts and suggest setting `AGENT_DATA_PYTHON` to an absolute Python 3.8 executable.
- Missing GUI support for `gen_box.py`: report checkpoint failure and suggest running in WSLg or X11.
- Missing YAML after manual annotation: pause and ask whether to retry annotation or skip clips.
- Missing gridmap: skip by default unless `use_gridmap=true`.
- Failed tracking for one YAML: continue collecting failures but do not silently mark the run successful.

## Testing Strategy

Local tests should not require ROS2, CUDA, GUI, or server paths.

Test with:

- temporary directories that mimic `raw_data`, `clip_data`, and `finish_data`
- dry-run command generation
- symlink planning
- segment selection parsing
- output validation
- log file creation and JSONL event schema
- isolated runtime command wrapping
- data runtime precheck behavior
- manual annotation post-check by pre-creating mock YAML files

Server-only integration should verify:

- ROS2 extraction
- synchronization
- GUI annotation checkpoint
- ONNX tracking
- full projection and trajectory outputs

## Implementation Order

1. Add VLA shared config, path helpers, command runner, and log writer.
2. Add isolated data runtime helpers and `vla_check_runtime`.
3. Add inspection and preparation tools.
4. Add extract/sync tools.
5. Add finish dataset and NoobScenes preparation tools.
6. Add manual annotation checkpoint tool.
7. Add tracking and projection/trajectory tools.
8. Add validation tool.
9. Update session prompt with VLA orchestration rules.
10. Add focused unit tests with dry-run, mock folders, and runtime wrapper checks.

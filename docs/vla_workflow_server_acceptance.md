# VLA workflow server acceptance

This document records the server-side acceptance steps for Task 15 of
`docs/superpowers/plans/2026-06-09-vla-multi-scene-workflow-implementation-plan.md`.

The helper script is:

```bash
scripts/vla_workflow_server_acceptance.sh
```

Use `--print-only` first on the server to inspect commands before running them.
The script keeps the server paths as defaults and does not invent
`AGENT_DATA_PYTHON` or `AGENT_DATA_ENV_SETUP`.

## Step 1: server environment check

Export or confirm these values on the server:

```bash
export VLA_RAW_ROOT=/media/heying/hy_data1/VLADatasets/raw_data
export VLA_CLIP_ROOT=/media/heying/hy_data1/VLADatasets/clip_data
export VLA_FINISH_ROOT=/media/heying/hy_data1/VLADatasets/finish_data
export VLA_DATA_TOOLBOX_SRC=/media/heying/hy_data2/GT_dog/modules_ros2/DataToolbox/src
export VLA_TRAJECTORY_ROOT=/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01
export VLA_GT_DOG_ROOT=/media/heying/hy_data2/GT_dog
export AGENT_DATA_PYTHON=/path/to/server/python3.8
export AGENT_DATA_ENV_SETUP=/path/to/server/data_env_setup.sh
export DASHSCOPE_API_KEY=/path-or-secret-managed-value
# Optional: export DJA_OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# Optional: export DJA_VLA_PLAN_MODEL=qwen3-max-2026-01-23
# Optional: export DJA_VLA_EXECUTOR_MODEL=qwen3-max-2026-01-23
```

`AGENT_DATA_PYTHON` and `AGENT_DATA_ENV_SETUP` must be confirmed from the
existing server run method. Do not downgrade Python or dependencies locally to
make this pass.

By default, `djx vla-workflow run` now uses real Plan-Agent and Executor-Agent
ReAct instances. If the server acceptance must exercise the old deterministic
path, pass `--agent-mode deterministic` explicitly or export
`DJA_VLA_WORKFLOW_AGENT_MODE=deterministic`; do not rely on silent fallback.

Preview:

```bash
bash scripts/vla_workflow_server_acceptance.sh --print-only check-env
```

Run:

```bash
bash scripts/vla_workflow_server_acceptance.sh check-env
```

## Step 2: 20270515 dry-run

Preview:

```bash
bash scripts/vla_workflow_server_acceptance.sh --print-only dry-run-20270515
```

Run:

```bash
bash scripts/vla_workflow_server_acceptance.sh dry-run-20270515
```

Expected plan:

- `extract_and_sync` variant is `u_legacy_topics`
- `sync.query_raw_dir` is `lidar_points`
- `gridmap_processing` uses `vla_prepare_gridmap/copy_existing_artifact` or
  `vla_prepare_gridmap/pointcloud_to_gridmap`
- `projection_and_trajectory` variant is `cjl_with_gridmap`
- `validate_outputs` variant is `expect_gridmap`

## Step 3: 20270605 dry-run

Preview:

```bash
bash scripts/vla_workflow_server_acceptance.sh --print-only dry-run-20270605
```

Run:

```bash
bash scripts/vla_workflow_server_acceptance.sh dry-run-20270605
```

Expected plan:

- `extract_and_sync` variant is `go2w_current_topics`
- `sync.query_raw_dir` is `rs32_lidar_points`
- calibration sensors end with `20260529_go2w/sensors`
- if an existing `grid_map` artifact exists, `gridmap_processing` uses
  `vla_prepare_gridmap/copy_existing_artifact`
- if no existing `grid_map` artifact exists, `gridmap_processing` uses
  `vla_prepare_gridmap/pointcloud_to_gridmap`
- `projection_and_trajectory` variant is `cjl_0525_with_gridmap`
- `validate_outputs` variant is `expect_gridmap`

## Step 4: 20270515 execution

Preview:

```bash
bash scripts/vla_workflow_server_acceptance.sh --print-only --confirm-execute execute-20270515
```

Run:

```bash
bash scripts/vla_workflow_server_acceptance.sh --confirm-execute execute-20270515
```

Manual checkpoint:

- workflow reaches `vla_run_manual_box_annotation` and pauses
- user completes GUI box annotation
- workflow continues only after YAML files exist

## Step 5: 20270605 grid_map precheck

Preview:

```bash
bash scripts/vla_workflow_server_acceptance.sh --print-only check-gridmap-20270605
```

Run:

```bash
bash scripts/vla_workflow_server_acceptance.sh check-gridmap-20270605 | head
```

If no path is printed, the Plan-Agent should choose
`vla_prepare_gridmap/pointcloud_to_gridmap`. Execution should block only when no
existing artifact is present and the pointcloud generator is unavailable.

## Step 6: 20270605 execution

Preview:

```bash
bash scripts/vla_workflow_server_acceptance.sh --print-only --confirm-execute execute-20270605
```

Run:

```bash
bash scripts/vla_workflow_server_acceptance.sh --confirm-execute execute-20270605
```

Expected execution:

- `vla_extract_and_sync` calls the current topic script variant
- `vla_prepare_finish_dataset` copies `20260529_go2w/sensors`
- `vla_prepare_gridmap` calls `copy_existing_artifact` or
  `pointcloud_to_gridmap`
- `vla_run_projection_and_trajectory` calls `2_othermethod_cjl_0525.py`
- `vla_run_projection_and_trajectory` does not call `cp_gridmap.py`
- `vla_validate_outputs` passes and checks `grid_map`

## Local verification

Before syncing to the server, run:

```bash
./.venv/bin/pytest tests/test_vla_workflow_server_acceptance_script.py -v
./.venv/bin/pytest tests/test_vla_workflow_dry_run_acceptance.py tests/test_vla_workflow_executor.py tests/test_vla_workflow_state_routing.py -v
```

Execution check: `djx vla-workflow run --approve` should emit `stage_executed`
messages after `approval_accepted`, and the run directory should contain
`stage_results.json`. If the payload only reports planning or confirmation state
and no stage result/log is written, stop the server acceptance run and inspect
the CLI executor loop before treating Step 4 or Step 6 as a real execution pass.

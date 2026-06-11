#!/usr/bin/env bash
set -euo pipefail

VLA_RAW_ROOT="${VLA_RAW_ROOT:-/media/heying/hy_data1/VLADatasets/raw_data}"
VLA_CLIP_ROOT="${VLA_CLIP_ROOT:-/media/heying/hy_data1/VLADatasets/clip_data}"
VLA_FINISH_ROOT="${VLA_FINISH_ROOT:-/media/heying/hy_data1/VLADatasets/finish_data}"
VLA_DATA_TOOLBOX_SRC="${VLA_DATA_TOOLBOX_SRC:-/media/heying/hy_data2/GT_dog/modules_ros2/DataToolbox/src}"
VLA_TRAJECTORY_ROOT="${VLA_TRAJECTORY_ROOT:-/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01}"
VLA_GT_DOG_ROOT="${VLA_GT_DOG_ROOT:-/media/heying/hy_data2/GT_dog}"
AGENT_DATA_PYTHON="${AGENT_DATA_PYTHON:-}"
AGENT_DATA_ENV_SETUP="${AGENT_DATA_ENV_SETUP:-}"

PRINT_ONLY=0
CONFIRM_EXECUTE=0

usage() {
  cat <<'USAGE'
Usage:
  scripts/vla_workflow_server_acceptance.sh [--print-only] [--confirm-execute] ACTION

Actions:
  check-env
  dry-run-20270515
  dry-run-20270605
  check-gridmap-20270605
  execute-20270515
  execute-20270605
  all-dry-run

Notes:
  --print-only prints the command instead of running it.
  execute-* actions require --confirm-execute.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --print-only)
      PRINT_ONLY=1
      shift
      ;;
    --confirm-execute)
      CONFIRM_EXECUTE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      break
      ;;
  esac
done

ACTION="${1:-}"
if [[ -z "$ACTION" ]]; then
  usage >&2
  exit 64
fi

print_env_exports() {
  cat <<EOF
export VLA_RAW_ROOT=${VLA_RAW_ROOT}
export VLA_CLIP_ROOT=${VLA_CLIP_ROOT}
export VLA_FINISH_ROOT=${VLA_FINISH_ROOT}
export VLA_DATA_TOOLBOX_SRC=${VLA_DATA_TOOLBOX_SRC}
export VLA_TRAJECTORY_ROOT=${VLA_TRAJECTORY_ROOT}
export VLA_GT_DOG_ROOT=${VLA_GT_DOG_ROOT}
export AGENT_DATA_PYTHON=${AGENT_DATA_PYTHON}
export AGENT_DATA_ENV_SETUP=${AGENT_DATA_ENV_SETUP}
EOF
}

require_dir() {
  local path="$1"
  local label="$2"
  if [[ ! -d "$path" ]]; then
    echo "missing ${label}: ${path}" >&2
    return 1
  fi
}

require_file() {
  local path="$1"
  local label="$2"
  if [[ ! -f "$path" ]]; then
    echo "missing ${label}: ${path}" >&2
    return 1
  fi
}

run_or_print() {
  if [[ "$PRINT_ONLY" -eq 1 ]]; then
    echo "$*"
    return 0
  fi
  "$@"
}

run_check_env() {
  if [[ "$PRINT_ONLY" -eq 1 ]]; then
    print_env_exports
    return 0
  fi

  print_env_exports
  require_dir "$VLA_RAW_ROOT" "VLA_RAW_ROOT"
  require_dir "$VLA_CLIP_ROOT" "VLA_CLIP_ROOT"
  require_dir "$VLA_FINISH_ROOT" "VLA_FINISH_ROOT"
  require_dir "$VLA_DATA_TOOLBOX_SRC" "VLA_DATA_TOOLBOX_SRC"
  require_dir "$VLA_TRAJECTORY_ROOT" "VLA_TRAJECTORY_ROOT"
  require_dir "$VLA_GT_DOG_ROOT" "VLA_GT_DOG_ROOT"

  if [[ -z "$AGENT_DATA_PYTHON" ]]; then
    echo "AGENT_DATA_PYTHON is required on the server; do not leave it empty." >&2
    return 1
  fi
  if [[ ! -x "$AGENT_DATA_PYTHON" ]]; then
    echo "AGENT_DATA_PYTHON is not executable: ${AGENT_DATA_PYTHON}" >&2
    return 1
  fi
  if [[ -n "$AGENT_DATA_ENV_SETUP" ]]; then
    require_file "$AGENT_DATA_ENV_SETUP" "AGENT_DATA_ENV_SETUP"
  fi
}

run_dry_run() {
  local date="$1"
  run_or_print djx vla-workflow run \
    --scenario navigation_vla \
    --date "$date" \
    --segments all \
    --scene-mode out \
    --dry-run
}

run_execute() {
  local date="$1"
  if [[ "$CONFIRM_EXECUTE" -ne 1 ]]; then
    echo "execute actions require --confirm-execute" >&2
    return 64
  fi
  run_or_print djx vla-workflow run \
    --scenario navigation_vla \
    --date "$date" \
    --segments all \
    --scene-mode out \
    --approve
}

run_gridmap_precheck_20270605() {
  if [[ "$PRINT_ONLY" -eq 1 ]]; then
    echo "find ${VLA_CLIP_ROOT}/20270605 -path '*sync_data*grid_map' -type d"
    return 0
  fi
  find "${VLA_CLIP_ROOT}/20270605" -path '*sync_data*grid_map' -type d
}

case "$ACTION" in
  check-env)
    run_check_env
    ;;
  dry-run-20270515)
    run_dry_run 20270515
    ;;
  dry-run-20270605)
    run_dry_run 20270605
    ;;
  check-gridmap-20270605)
    run_gridmap_precheck_20270605
    ;;
  execute-20270515)
    run_execute 20270515
    ;;
  execute-20270605)
    run_execute 20270605
    ;;
  all-dry-run)
    run_check_env
    run_dry_run 20270515
    run_dry_run 20270605
    run_gridmap_precheck_20270605
    ;;
  *)
    echo "unknown action: ${ACTION}" >&2
    usage >&2
    exit 64
    ;;
esac

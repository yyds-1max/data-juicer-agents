from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "vla_workflow_server_acceptance.sh"


def _run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )


def test_server_acceptance_script_prints_environment_exports():
    result = _run_script("--print-only", "check-env")

    assert result.returncode == 0
    assert "export VLA_RAW_ROOT=/media/heying/hy_data1/VLADatasets/raw_data" in result.stdout
    assert "export VLA_CLIP_ROOT=/media/heying/hy_data1/VLADatasets/clip_data" in result.stdout
    assert "export VLA_FINISH_ROOT=/media/heying/hy_data1/VLADatasets/finish_data" in result.stdout
    assert (
        "export VLA_DATA_TOOLBOX_SRC=/media/heying/hy_data2/GT_dog/modules_ros2/"
        "DataToolbox/src"
    ) in result.stdout
    assert (
        "export VLA_TRAJECTORY_ROOT=/media/heying/hy_data1/Trajectory_visualization/"
        "Object_location_gh_v3_fisheye_five_U_add_SF_01"
    ) in result.stdout
    assert "export VLA_GT_DOG_ROOT=/media/heying/hy_data2/GT_dog" in result.stdout
    assert "export AGENT_DATA_PYTHON=" in result.stdout
    assert "export AGENT_DATA_ENV_SETUP=" in result.stdout


def test_server_acceptance_script_prints_dry_run_commands_for_both_dates():
    result_20270515 = _run_script("--print-only", "dry-run-20270515")
    result_20270605 = _run_script("--print-only", "dry-run-20270605")

    assert result_20270515.returncode == 0
    assert "djx vla-workflow run" in result_20270515.stdout
    assert "--scenario navigation_vla" in result_20270515.stdout
    assert "--date 20270515" in result_20270515.stdout
    assert "--segments all" in result_20270515.stdout
    assert "--scene-mode out" in result_20270515.stdout
    assert "--dry-run" in result_20270515.stdout

    assert result_20270605.returncode == 0
    assert "--date 20270605" in result_20270605.stdout
    assert "--dry-run" in result_20270605.stdout


def test_server_acceptance_script_prints_gridmap_precheck_for_20270605():
    result = _run_script("--print-only", "check-gridmap-20270605")

    assert result.returncode == 0
    assert (
        "find /media/heying/hy_data1/VLADatasets/clip_data/20270605 "
        "-path '*sync_data*grid_map' -type d"
    ) in result.stdout


def test_server_acceptance_script_requires_confirmation_for_execute_actions():
    blocked = _run_script("--print-only", "execute-20270515")
    confirmed = _run_script("--print-only", "--confirm-execute", "execute-20270515")

    assert blocked.returncode != 0
    assert "--confirm-execute" in blocked.stderr
    assert confirmed.returncode == 0
    assert "--date 20270515" in confirmed.stdout
    assert "--approve" in confirmed.stdout


def test_server_acceptance_script_prints_execute_command_for_20270605():
    result = _run_script("--print-only", "--confirm-execute", "execute-20270605")

    assert result.returncode == 0
    assert "djx vla-workflow run" in result.stdout
    assert "--date 20270605" in result.stdout
    assert "--approve" in result.stdout

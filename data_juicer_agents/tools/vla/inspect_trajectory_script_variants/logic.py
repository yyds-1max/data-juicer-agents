from __future__ import annotations

from pathlib import Path
from typing import Any


def inspect_trajectory_script_variants(
    *,
    trajectory_root: str,
    run_id: str | None = None,
    log_dir: str | None = None,
) -> dict[str, Any]:
    root = Path(trajectory_root).expanduser()
    cjl = root / "2_pt_project" / "2_othermethod_cjl.py"
    cjl_0525 = root / "2_pt_project" / "2_othermethod_cjl_0525.py"
    move = root / "2_pt_project" / "3_move_dir.py"
    cp_gridmap = root / "other_code" / "cp_gridmap.py"
    projection_implicit = False
    for script in (cjl, cjl_0525):
        if script.is_file() and "cp_gridmap.py" in script.read_text(
            encoding="utf-8", errors="ignore"
        ):
            projection_implicit = True
    return {
        "ok": True,
        "trajectory_root": str(root),
        "variants": {
            "cjl_with_gridmap": {"available": cjl.is_file(), "script": str(cjl)},
            "cjl_0525_with_gridmap": {
                "available": cjl_0525.is_file(),
                "script": str(cjl_0525),
            },
            "move_gridmap": {"available": move.is_file(), "script": str(move)},
        },
        "cp_gridmap_script": {"available": cp_gridmap.is_file(), "script": str(cp_gridmap)},
        "projection_implicitly_calls_cp_gridmap": projection_implicit,
        "warnings": (
            [
                {
                    "type": "projection_implicitly_calls_cp_gridmap",
                    "message": "Projection scripts still reference cp_gridmap.py.",
                }
            ]
            if projection_implicit
            else []
        ),
        "run_id": run_id,
        "log_dir": log_dir,
    }

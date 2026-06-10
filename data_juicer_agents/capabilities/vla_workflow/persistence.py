from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from data_juicer_agents.core.tool import ToolContext

PLANNING_NOTES_FILE = "planning_notes.json"
OBSERVATIONS_FILE = "observations.json"
DATA_PROFILE_FILE = "data_profile.json"
PLAN_FILE = "plan.json"


def _json_path(run_dir: str | Path, filename: str) -> Path:
    return Path(run_dir).expanduser() / filename


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _timestamp(created_at: datetime | None = None) -> str:
    value = created_at or datetime.now(timezone.utc)
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y%m%d%H%M%S")


def make_workflow_run_id(
    *,
    scenario: str,
    date: str,
    created_at: datetime | None = None,
) -> str:
    if not str(scenario).strip():
        raise ValueError("scenario is required")
    if not str(date).strip():
        raise ValueError("date is required")
    return f"vla_{scenario}_{date}_{_timestamp(created_at)}"


def build_workflow_run_dir(
    ctx: ToolContext | None = None,
    *,
    scenario: str,
    date: str,
    run_id: str | None = None,
    created_at: datetime | None = None,
    create: bool = True,
) -> Path:
    root = ctx.resolve_artifacts_dir() if ctx is not None else Path("./.djx").expanduser()
    resolved_run_id = run_id or make_workflow_run_id(
        scenario=scenario,
        date=date,
        created_at=created_at,
    )
    run_dir = root / "vla_workflow_runs" / str(date) / resolved_run_id
    if create:
        run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_planning_notes(run_dir: Path, payload: dict) -> Path:
    return _write_json(_json_path(run_dir, PLANNING_NOTES_FILE), dict(payload))


def append_observation(run_dir: Path, payload: dict) -> Path:
    path = _json_path(run_dir, OBSERVATIONS_FILE)
    observations = _read_json(path) if path.exists() else []
    if not isinstance(observations, list):
        raise ValueError("observations.json must contain a JSON list")
    observations.append(dict(payload))
    return _write_json(path, observations)


def save_data_profile(run_dir: Path, payload: dict) -> Path:
    return _write_json(_json_path(run_dir, DATA_PROFILE_FILE), dict(payload))


def save_workflow_plan(run_dir: Path, payload: dict) -> Path:
    return _write_json(_json_path(run_dir, PLAN_FILE), dict(payload))


def load_workflow_artifacts(run_dir: Path) -> dict[str, Any]:
    root = Path(run_dir).expanduser()
    artifact_files: Mapping[str, str] = {
        "planning_notes": PLANNING_NOTES_FILE,
        "observations": OBSERVATIONS_FILE,
        "data_profile": DATA_PROFILE_FILE,
        "plan": PLAN_FILE,
    }
    return {
        artifact_name: (
            _read_json(root / filename) if (root / filename).exists() else None
        )
        for artifact_name, filename in artifact_files.items()
    }


__all__ = [
    "DATA_PROFILE_FILE",
    "OBSERVATIONS_FILE",
    "PLAN_FILE",
    "PLANNING_NOTES_FILE",
    "append_observation",
    "build_workflow_run_dir",
    "load_workflow_artifacts",
    "make_workflow_run_id",
    "save_data_profile",
    "save_planning_notes",
    "save_workflow_plan",
]

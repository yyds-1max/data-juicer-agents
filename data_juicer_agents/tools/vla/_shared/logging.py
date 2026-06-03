from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _json_dump(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _format_command(command: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in command)


@dataclass(frozen=True)
class VLARunLogger:
    run_dir: Path

    @classmethod
    def create(cls, *, root: str | Path, date: str, run_id: str) -> VLARunLogger:
        run_dir = Path(root).expanduser() / "vla_runs" / date / run_id
        return cls.open(run_dir)

    @classmethod
    def open(cls, run_dir: str | Path) -> VLARunLogger:
        path = Path(run_dir).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        for name in ("events.jsonl", "commands.log", "stdout.log", "stderr.log"):
            (path / name).touch(exist_ok=True)
        return cls(run_dir=path)

    def write_run_metadata(self, payload: Mapping[str, Any]) -> None:
        _json_dump(self.run_dir / "run.json", payload)

    def write_summary(self, payload: Mapping[str, Any]) -> None:
        _json_dump(self.run_dir / "summary.json", payload)

    def event(
        self,
        *,
        stage: str,
        event_type: str,
        ok: bool,
        message: str = "",
        data: Mapping[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "timestamp": _now(),
            "stage": stage,
            "event_type": event_type,
            "ok": bool(ok),
            "message": str(message),
        }
        if data:
            payload["data"] = dict(data)

        with (self.run_dir / "events.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def command(
        self,
        *,
        stage: str,
        command: Iterable[str],
        cwd: str,
        return_code: int | None,
        stdout: str,
        stderr: str,
    ) -> None:
        with (self.run_dir / "commands.log").open("a", encoding="utf-8") as fh:
            fh.write(f"[{_now()}] stage={stage} cwd={cwd} return_code={return_code}\n")
            fh.write(f"command: {_format_command(command)}\n\n")

        with (self.run_dir / "stdout.log").open("a", encoding="utf-8") as fh:
            fh.write(f"----- {stage} {_now()} -----\n{stdout}\n")

        with (self.run_dir / "stderr.log").open("a", encoding="utf-8") as fh:
            fh.write(f"----- {stage} {_now()} -----\n{stderr}\n")

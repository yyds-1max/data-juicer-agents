from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


def validate_date(date: str) -> str:
    value = str(date).strip()
    if not re.fullmatch(r"\d{8}", value):
        raise ValueError("date must be an 8 digit string such as 20270515")
    return value


def sorted_child_dirs(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted([item for item in path.iterdir() if item.is_dir()], key=lambda p: p.name)


def normalize_selected_segments(selected: Iterable[str]) -> list[str]:
    return [str(item).strip() for item in selected if str(item).strip()]

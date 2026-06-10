from __future__ import annotations

from typing import Any


def get_manipulation_template() -> dict[str, Any]:
    return {
        "scenario": "manipulation_vla",
        "status": "unsupported",
        "message": "当前机械臂 VLA 数据处理功能尚未开放，第一版只支持 navigation_vla。",
    }


__all__ = ["get_manipulation_template"]

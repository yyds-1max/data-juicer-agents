"""Workflow skeleton templates for VLA scenarios."""

from .manipulation import get_manipulation_template
from .navigation import (
    NAVIGATION_HUMAN_CHECKPOINTS,
    NAVIGATION_STAGE_ORDER,
    get_navigation_template,
)

__all__ = [
    "NAVIGATION_HUMAN_CHECKPOINTS",
    "NAVIGATION_STAGE_ORDER",
    "get_manipulation_template",
    "get_navigation_template",
]

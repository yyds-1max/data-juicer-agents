from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _path_env(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


@dataclass(frozen=True)
class VLAPaths:
    raw_root: Path = field(
        default_factory=lambda: _path_env(
            "VLA_RAW_ROOT", "/media/heying/hy_data1/VLADatasets/raw_data"
        )
    )
    clip_root: Path = field(
        default_factory=lambda: _path_env(
            "VLA_CLIP_ROOT", "/media/heying/hy_data1/VLADatasets/clip_data"
        )
    )
    finish_root: Path = field(
        default_factory=lambda: _path_env(
            "VLA_FINISH_ROOT", "/media/heying/hy_data1/VLADatasets/finish_data"
        )
    )
    data_toolbox_src: Path = field(
        default_factory=lambda: _path_env(
            "VLA_DATA_TOOLBOX_SRC",
            "/media/heying/hy_data2/GT_dog/modules_ros2/DataToolbox/src",
        )
    )
    trajectory_root: Path = field(
        default_factory=lambda: _path_env(
            "VLA_TRAJECTORY_ROOT",
            "/media/heying/hy_data1/Trajectory_visualization/"
            "Object_location_gh_v3_fisheye_five_U_add_SF_01",
        )
    )
    gt_dog_root: Path = field(
        default_factory=lambda: _path_env(
            "VLA_GT_DOG_ROOT", "/media/heying/hy_data2/GT_dog"
        )
    )

    def raw_date_dir(self, date: str) -> Path:
        return self.raw_root / date

    def raw_temp_dir(self, date: str) -> Path:
        return self.raw_root / f"{date}_temp"

    def clip_date_dir(self, date: str) -> Path:
        return self.clip_root / date

    def finish_date_dir(self, date: str) -> Path:
        return self.finish_root / date

    def finish_temp_dir(self, date: str) -> Path:
        return self.finish_root / f"{date}_temp"

    @property
    def ros2_setup_bash(self) -> Path:
        return (
            self.gt_dog_root
            / "modules"
            / "message"
            / "ros2"
            / "install"
            / "setup.bash"
        )

    @property
    def ros2_ws_setup_bash(self) -> Path:
        return (
            self.gt_dog_root
            / "modules"
            / "ros2_ws"
            / "src"
            / "install"
            / "setup.bash"
        )

    @property
    def shm_msgs_lib_dir(self) -> Path:
        return (
            self.gt_dog_root
            / "modules"
            / "message"
            / "shm"
            / "install"
            / "shm_msgs"
            / "lib"
        )


def _runtime_env_setup() -> Path | None:
    value = os.environ.get("AGENT_DATA_ENV_SETUP")
    if not value:
        return None
    return Path(value).expanduser()


@dataclass(frozen=True)
class VLARuntime:
    data_python: str = field(
        default_factory=lambda: os.environ.get("AGENT_DATA_PYTHON", "python3")
    )
    data_env_setup: Path | None = field(default_factory=_runtime_env_setup)

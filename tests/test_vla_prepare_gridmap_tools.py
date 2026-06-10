from data_juicer_agents.tools.vla.prepare_gridmap.logic import prepare_gridmap
from data_juicer_agents.tools.vla.prepare_gridmap.tool import VLA_PREPARE_GRIDMAP


def test_prepare_gridmap_copy_existing_artifact_copies_grid_map_to_finish_temp(tmp_path):
    clip_gridmap = (
        tmp_path
        / "clip"
        / "20270515"
        / "20260515_102948"
        / "sync_data"
        / "20260515_102948_zhigu_wuhan_0"
        / "grid_map"
    )
    clip_gridmap.mkdir(parents=True)
    (clip_gridmap / "1778812189469693651.json").write_text("{}\n", encoding="utf-8")
    finish_temp_clip = (
        tmp_path
        / "finish"
        / "20270515_temp"
        / "samples"
        / "20270515"
        / "20260515_102948_zhigu_wuhan_0"
    )
    finish_temp_clip.mkdir(parents=True)

    result = prepare_gridmap(
        date="20270515",
        selected_segments=["20260515_102948"],
        clip_root=str(tmp_path / "clip"),
        finish_root=str(tmp_path / "finish"),
        trajectory_root=str(tmp_path / "traj"),
        gridmap_variant="copy_existing_artifact",
        dry_run=False,
    )

    copied = finish_temp_clip / "grid_map" / "1778812189469693651.json"
    assert result["ok"] is True
    assert copied.is_file()
    assert result["prepared_gridmap_count"] == 1
    assert result["prepared_paths"] == [str(finish_temp_clip / "grid_map")]


def test_prepare_gridmap_pointcloud_to_gridmap_dry_run_builds_generator_command(tmp_path):
    generator = tmp_path / "traj" / "other_code" / "pcd_to_grid.py"
    generator.parent.mkdir(parents=True)
    generator.write_text("# generator placeholder\n", encoding="utf-8")

    result = prepare_gridmap(
        date="20270605",
        selected_segments=["20260605_152856"],
        clip_root=str(tmp_path / "clip"),
        finish_root=str(tmp_path / "finish"),
        trajectory_root=str(tmp_path / "traj"),
        gridmap_variant="pointcloud_to_gridmap",
        data_python="/usr/bin/python3.8",
        data_env_setup="/srv/setup.sh",
        dry_run=True,
    )

    joined = "\n".join(" ".join(command) for command in result["commands"])
    assert result["ok"] is True
    assert "pcd_to_grid.py" in joined
    assert "--base-path" in joined
    assert "--date 20270605" in joined
    assert "--segments 20260605_152856" in joined


def test_prepare_gridmap_tool_spec_is_registered_shape():
    assert VLA_PREPARE_GRIDMAP.name == "vla_prepare_gridmap"
    assert VLA_PREPARE_GRIDMAP.effects == "execute"
    assert VLA_PREPARE_GRIDMAP.confirmation == "required"

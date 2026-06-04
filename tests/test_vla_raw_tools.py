from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.tools.vla.inspect_raw_date.logic import inspect_raw_date
from data_juicer_agents.tools.vla.inspect_raw_date.tool import VLA_INSPECT_RAW_DATE
from data_juicer_agents.tools.vla.prepare_raw_temp.input import PrepareRawTempInput
from data_juicer_agents.tools.vla.prepare_raw_temp.logic import prepare_raw_temp
from data_juicer_agents.tools.vla.prepare_raw_temp.tool import VLA_PREPARE_RAW_TEMP


def test_inspect_raw_date_lists_segments_and_db3_presence(tmp_path):
    raw_root = tmp_path / "raw_data"
    seg = raw_root / "20270515" / "20260515_102948"
    seg.mkdir(parents=True)
    (seg / "metadata.yaml").write_text(
        "rosbag2_bagfile_information: {}\n", encoding="utf-8"
    )
    (seg / "0515_102948_0.db3").write_text("", encoding="utf-8")

    result = inspect_raw_date(date="20270515", raw_root=str(raw_root))

    assert result["ok"] is True
    assert result["segments"][0]["name"] == "20260515_102948"
    assert result["segments"][0]["has_metadata"] is True
    assert result["segments"][0]["has_db3"] is True


def test_inspect_raw_date_reports_missing_date_without_creating_logs(tmp_path):
    result = inspect_raw_date(date="20270515", raw_root=str(tmp_path / "raw_data"))

    assert result["ok"] is False
    assert result["error_type"] == "missing_raw_date"
    assert result["segments"] == []


def test_prepare_raw_temp_dry_run_reports_symlink_plan(tmp_path):
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    (raw_root / "20270515" / "seg_a").mkdir(parents=True)

    result = prepare_raw_temp(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["dry_run"] is True
    assert result["links"][0]["source"].endswith("raw_data/20270515/seg_a")
    assert result["links"][0]["target"].endswith("raw_data/20270515_temp/seg_a")
    assert not (raw_root / "20270515_temp").exists()


def test_prepare_raw_temp_dry_run_reports_owner_and_empty_skipped_segments(tmp_path):
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    (raw_root / "20270515" / "seg_a").mkdir(parents=True)

    result = prepare_raw_temp(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        owner="heying:heying",
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["owner"] == "heying:heying"
    assert result["skipped_segments"] == []
    assert not (raw_root / "20270515_temp").exists()
    assert not (clip_root / "20270515").exists()


def test_prepare_raw_temp_execute_creates_symlink_and_clip_dir(tmp_path):
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    (raw_root / "20270515" / "seg_a").mkdir(parents=True)

    result = prepare_raw_temp(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        dry_run=False,
    )

    assert result["ok"] is True
    assert (clip_root / "20270515").is_dir()
    assert (raw_root / "20270515_temp" / "seg_a").exists()


def test_prepare_raw_temp_reports_missing_segments(tmp_path):
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    (raw_root / "20270515").mkdir(parents=True)

    result = prepare_raw_temp(
        date="20270515",
        selected_segments=["seg_missing"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["error_type"] == "missing_segments"
    assert result["missing_segments"] == ["seg_missing"]
    assert result["skipped_segments"] == [
        {
            "segment": "seg_missing",
            "reason": "missing_source",
            "source": str(raw_root / "20270515" / "seg_missing"),
            "target": str(raw_root / "20270515_temp" / "seg_missing"),
        }
    ]
    assert not (raw_root / "20270515_temp").exists()


def test_prepare_raw_temp_does_not_overwrite_existing_non_symlink_target(tmp_path):
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    (raw_root / "20270515" / "seg_a").mkdir(parents=True)
    target = raw_root / "20270515_temp" / "seg_a"
    target.mkdir(parents=True)
    marker = target / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    result = prepare_raw_temp(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        dry_run=False,
    )

    assert result["ok"] is True
    assert target.is_dir()
    assert not target.is_symlink()
    assert marker.read_text(encoding="utf-8") == "keep"
    assert result["skipped_segments"] == [
        {
            "segment": "seg_a",
            "reason": "target_exists_not_symlink",
            "source": str(raw_root / "20270515" / "seg_a"),
            "target": str(target),
        }
    ]


def test_prepare_raw_temp_input_accepts_owner_field():
    parsed = PrepareRawTempInput.model_validate(
        {
            "date": "20270515",
            "selected_segments": ["seg_a"],
            "owner": "heying:heying",
        }
    )

    assert parsed.owner == "heying:heying"


def test_prepare_raw_temp_chown_uses_argv_for_managed_directories(tmp_path, monkeypatch):
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    (raw_root / "20270515" / "seg_a").mkdir(parents=True)
    calls = []

    def fake_run(command, check, stdout, stderr, text):
        calls.append(
            {
                "command": command,
                "check": check,
                "stdout": stdout,
                "stderr": stderr,
                "text": text,
            }
        )

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "data_juicer_agents.tools.vla.prepare_raw_temp.logic.subprocess.run",
        fake_run,
    )

    result = prepare_raw_temp(
        date="20270515",
        selected_segments=["seg_a"],
        raw_root=str(raw_root),
        clip_root=str(clip_root),
        owner="heying:heying",
        dry_run=False,
    )

    assert result["ok"] is True
    assert [call["command"] for call in calls] == [
        ["chown", "-R", "heying:heying", str(raw_root / "20270515_temp")],
        ["chown", "-R", "heying:heying", str(clip_root / "20270515")],
    ]
    assert all(call["check"] is False for call in calls)


def test_raw_tool_specs_wrap_logic_results(tmp_path):
    raw_root = tmp_path / "raw_data"
    clip_root = tmp_path / "clip_data"
    (raw_root / "20270515" / "seg_a").mkdir(parents=True)

    inspect_result = VLA_INSPECT_RAW_DATE.execute(
        ToolContext(working_dir=str(tmp_path)),
        {"date": "20270515", "raw_root": str(raw_root)},
    )
    prepare_result = VLA_PREPARE_RAW_TEMP.execute(
        ToolContext(working_dir=str(tmp_path)),
        {
            "date": "20270515",
            "selected_segments": ["seg_a"],
            "raw_root": str(raw_root),
            "clip_root": str(clip_root),
            "owner": "heying:heying",
            "dry_run": True,
        },
    )

    assert inspect_result.ok is True
    assert inspect_result.data["count"] == 1
    assert prepare_result.ok is True
    assert prepare_result.data["links"][0]["segment"] == "seg_a"
    assert prepare_result.data["owner"] == "heying:heying"

import json

from data_juicer_agents.tools.vla._shared.logging import VLARunLogger


def test_vla_run_logger_writes_metadata_events_and_summary(tmp_path):
    logger = VLARunLogger.create(root=tmp_path, date="20270515", run_id="run_test")

    logger.write_run_metadata({"date": "20270515", "selected_segments": ["seg_a"]})
    logger.event(
        stage="inspect",
        event_type="stage_end",
        ok=True,
        message="done",
        data={"count": 1},
    )
    logger.command(
        stage="inspect",
        command=["echo", "ok"],
        cwd="/tmp/work",
        return_code=0,
        stdout="ok\n",
        stderr="",
    )
    logger.write_summary({"status": "completed", "completed_stages": ["inspect"]})

    assert (
        json.loads((logger.run_dir / "run.json").read_text(encoding="utf-8"))["date"]
        == "20270515"
    )
    events = (
        (logger.run_dir / "events.jsonl")
        .read_text(encoding="utf-8")
        .strip()
        .splitlines()
    )
    assert len(events) == 1
    assert json.loads(events[0])["stage"] == "inspect"
    assert "echo ok" in (logger.run_dir / "commands.log").read_text(
        encoding="utf-8"
    )
    assert "ok\n" in (logger.run_dir / "stdout.log").read_text(encoding="utf-8")
    assert (
        json.loads((logger.run_dir / "summary.json").read_text(encoding="utf-8"))[
            "status"
        ]
        == "completed"
    )

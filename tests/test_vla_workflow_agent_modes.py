from __future__ import annotations

from pathlib import Path

from data_juicer_agents.capabilities.vla_workflow.service import execute_vla_workflow
from data_juicer_agents.core.tool import ToolContext
from data_juicer_agents.tools.vla.run_workflow.input import RunWorkflowInput


def _ctx(tmp_path: Path) -> ToolContext:
    return ToolContext(working_dir=str(tmp_path), artifacts_dir=str(tmp_path))


def test_default_react_mode_fails_without_silent_fallback(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_API_TOKEN", raising=False)

    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="react-missing-key",
        ),
        tool_context=_ctx(tmp_path),
    )

    assert result.exit_code == 2
    assert result.payload["ok"] is False
    assert result.payload["agent_mode"] == "react"
    assert result.payload["fallback_used"] is False
    assert result.payload["error_type"] == "react_agent_unavailable"
    assert "deterministic fallback is disabled" in result.payload["message"]


def test_react_with_deterministic_fallback_is_visible(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("MODELSCOPE_API_TOKEN", raising=False)
    monkeypatch.setenv("VLA_RAW_ROOT", str(tmp_path / "raw_data"))
    monkeypatch.setenv("VLA_CLIP_ROOT", str(tmp_path / "clip_data"))
    monkeypatch.setenv("VLA_FINISH_ROOT", str(tmp_path / "finish_data"))
    monkeypatch.setenv("VLA_TRAJECTORY_ROOT", str(tmp_path / "trajectory"))

    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="fallback-visible",
            agent_mode="react-with-deterministic-fallback",
        ),
        tool_context=_ctx(tmp_path),
    )

    assert result.payload["agent_mode"] == "deterministic"
    assert result.payload["requested_agent_mode"] == "react-with-deterministic-fallback"
    assert result.payload["fallback_used"] is True
    assert "Missing API key" in result.payload["fallback_reason"]
    assert any(
        item["type"] == "react_agent_fallback" for item in result.payload["messages"]
    )
    assert "deterministic fallback" in result.payload["user_message"]


def test_explicit_deterministic_mode_uses_legacy_planning_path(tmp_path: Path):
    result = execute_vla_workflow(
        RunWorkflowInput(
            date="20270515",
            dry_run=True,
            approve=False,
            run_id="deterministic-explicit",
            agent_mode="deterministic",
        ),
        tool_context=_ctx(tmp_path),
    )

    assert result.payload["agent_mode"] == "deterministic"
    assert result.payload["requested_agent_mode"] == "deterministic"
    assert result.payload["fallback_used"] is False
    assert "fallback_reason" not in result.payload

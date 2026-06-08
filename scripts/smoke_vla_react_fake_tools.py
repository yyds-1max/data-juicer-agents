#!/usr/bin/env python
"""Smoke-test VLA ReAct orchestration with fake tool results.

This script uses the real session prompt, real AgentScope ReActAgent, and a real
LLM call, but replaces VLA tool executors with deterministic fake results. It is
intended to answer: "Will the agent choose the right VLA tools in order?"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from data_juicer_agents.adapters.agentscope.tools import build_agentscope_json_schema
from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent
from data_juicer_agents.core.tool import ToolContext, ToolResult, ToolSpec
from data_juicer_agents.tools.vla.registry import TOOL_SPECS as VLA_TOOL_SPECS
from data_juicer_agents.utils.runtime_helpers import to_text_response


DEFAULT_EXPECTED_CHAIN = [
    "vla_inspect_raw_date",
    "vla_check_runtime",
    "vla_prepare_raw_temp",
    "vla_extract_and_sync",
    "vla_list_clip_segments",
    "vla_prepare_finish_dataset",
    "vla_build_noobscenes_inputs",
    "vla_run_manual_box_annotation",
    "vla_run_tracking",
    "vla_run_projection_and_trajectory",
    "vla_validate_outputs",
]

VLA_SPEC_BY_NAME = {spec.name: spec for spec in VLA_TOOL_SPECS}


@dataclass
class FakeToolCall:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]


@dataclass
class FakeVLAToolState:
    date: str
    raw_segments: list[str]
    clip_segments: list[str]
    scene_mode: str
    use_gridmap: bool
    calls: list[FakeToolCall] = field(default_factory=list)

    @property
    def clip_names(self) -> list[str]:
        return [
            f"{segment}_zhigu_wuhan_0"
            for segment in self.clip_segments
        ]

    @property
    def raw_root(self) -> str:
        return os.environ.get("VLA_RAW_ROOT", "/media/heying/hy_data1/VLADatasets/raw_data")

    @property
    def clip_root(self) -> str:
        return os.environ.get("VLA_CLIP_ROOT", "/media/heying/hy_data1/VLADatasets/clip_data")

    @property
    def finish_root(self) -> str:
        return os.environ.get("VLA_FINISH_ROOT", "/media/heying/hy_data1/VLADatasets/finish_data")

    @property
    def trajectory_root(self) -> str:
        return os.environ.get(
            "VLA_TRAJECTORY_ROOT",
            "/media/heying/hy_data1/Trajectory_visualization/Object_location_gh_v3_fisheye_five_U_add_SF_01",
        )

    def result_for(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
            "vla_inspect_raw_date": self._inspect_raw_date,
            "vla_check_runtime": self._check_runtime,
            "vla_prepare_raw_temp": self._prepare_raw_temp,
            "vla_extract_and_sync": self._extract_and_sync,
            "vla_list_clip_segments": self._list_clip_segments,
            "vla_prepare_finish_dataset": self._prepare_finish_dataset,
            "vla_build_noobscenes_inputs": self._build_noobscenes_inputs,
            "vla_run_manual_box_annotation": self._run_manual_box_annotation,
            "vla_run_tracking": self._run_tracking,
            "vla_run_projection_and_trajectory": self._run_projection_and_trajectory,
            "vla_validate_outputs": self._validate_outputs,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return {
                "ok": False,
                "error_type": "unexpected_tool",
                "message": f"No simulated result is configured for {tool_name}",
            }
        payload = handler(args)
        payload.setdefault("ok", True)
        self.calls.append(FakeToolCall(tool_name, dict(args), dict(payload)))
        return payload

    def _inspect_raw_date(self, args: dict[str, Any]) -> dict[str, Any]:
        date = str(args.get("date") or self.date)
        return {
            "ok": True,
            "date": date,
            "raw_root": self.raw_root,
            "segments": [
                {
                    "name": segment,
                    "path": f"{self.raw_root}/{date}/{segment}",
                    "db3_count": 1,
                    "db3_files": [f"{self.raw_root}/{date}/{segment}/{segment}.db3"],
                }
                for segment in self.raw_segments
            ],
            "count": len(self.raw_segments),
        }

    def _check_runtime(self, _args: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "runtime": "configured",
            "python": os.environ.get("AGENT_DATA_PYTHON", "/usr/bin/python3.8"),
            "checks": [
                {"name": "data_python", "ok": True},
                {"name": "data_env_setup", "ok": True},
                {"name": "trajectory_root", "ok": True},
            ],
        }

    def _prepare_raw_temp(self, args: dict[str, Any]) -> dict[str, Any]:
        selected = _list_arg(args.get("selected_segments")) or self.raw_segments
        return {
            "ok": True,
            "date": str(args.get("date") or self.date),
            "dry_run": bool(args.get("dry_run", False)),
            "selected_segments": selected,
            "links": [
                {
                    "segment": segment,
                    "source": f"{self.raw_root}/{self.date}/{segment}",
                    "target": f"{self.raw_root}/{self.date}_temp/{segment}",
                    "status": "created",
                }
                for segment in selected
            ],
            "skipped_segments": [],
        }

    def _extract_and_sync(self, args: dict[str, Any]) -> dict[str, Any]:
        selected = _list_arg(args.get("selected_segments")) or self.raw_segments
        return {
            "ok": True,
            "date": str(args.get("date") or self.date),
            "dry_run": bool(args.get("dry_run", False)),
            "selected_segments": selected,
            "completed_segments": selected,
            "failed_segments": [],
            "segments": [
                {
                    "name": segment,
                    "save_path": f"{self.clip_root}/{self.date}/{segment}",
                    "sync_output_dir": "sync_data",
                }
                for segment in selected
            ],
        }

    def _list_clip_segments(self, args: dict[str, Any]) -> dict[str, Any]:
        date = str(args.get("date") or self.date)
        return {
            "ok": True,
            "date": date,
            "clip_root": self.clip_root,
            "segments": [
                {
                    "name": segment,
                    "path": f"{self.clip_root}/{date}/{segment}",
                    "sync_data_dir": f"{self.clip_root}/{date}/{segment}/sync_data",
                    "has_sync_data": True,
                }
                for segment in self.clip_segments
            ],
            "count": len(self.clip_segments),
        }

    def _prepare_finish_dataset(self, args: dict[str, Any]) -> dict[str, Any]:
        selected = _list_arg(args.get("selected_segments")) or self.clip_segments
        clip_names = [f"{segment}_zhigu_wuhan_0" for segment in selected]
        return {
            "ok": True,
            "date": str(args.get("date") or self.date),
            "scene_mode": str(args.get("scene_mode") or self.scene_mode),
            "selected_segments": selected,
            "save_path": f"{self.finish_root}/{self.date}",
            "save_path_temp": f"{self.finish_root}/{self.date}_temp",
            "clips": [
                {
                    "clip_name": clip,
                    "target": f"{self.finish_root}/{self.date}_temp/samples/{self.date}/{clip}",
                    "copied_subdirs": ["fisheye_front", "r32_rslidar_points", "sensors"],
                }
                for clip in clip_names
            ],
            "clip_count": len(clip_names),
            "missing_sync_data": [],
            "missing_subdirectories": [],
        }

    def _build_noobscenes_inputs(self, _args: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "save_path_temp": f"{self.finish_root}/{self.date}_temp",
            "trajectory_root": self.trajectory_root,
            "clips": [
                {
                    "clip_name": clip,
                    "metadata_json": f"{self.finish_root}/{self.date}_temp/samples/{self.date}/{clip}/{clip}.json",
                    "video_path": f"{self.finish_root}/{self.date}_temp/samples/{self.date}/{clip}/dog.mp4",
                }
                for clip in self.clip_names
            ],
            "warnings": [],
        }

    def _run_manual_box_annotation(self, _args: dict[str, Any]) -> dict[str, Any]:
        yaml_paths = [
            f"{self.finish_root}/{self.date}_temp/samples/{self.date}/{clip}/master_black_black_purple.yaml"
            for clip in self.clip_names
        ]
        return {
            "ok": True,
            "checkpoint_message": "Manual annotation completed and YAML files were found.",
            "yaml_paths": yaml_paths,
            "missing_yaml_clips": [],
        }

    def _run_tracking(self, _args: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "yaml_count": len(self.clip_names),
            "completed_jobs": [
                {
                    "clip_name": clip,
                    "moved_outputs": [
                        {"kind": "dir", "moved": True, "target": f"{clip}/tracking_img_master_black_black_purple"},
                        {"kind": "file", "moved": True, "target": f"{clip}/img_master_black_black_purple.txt"},
                    ],
                }
                for clip in self.clip_names
            ],
            "failed_yaml_paths": [],
        }

    def _run_projection_and_trajectory(self, args: dict[str, Any]) -> dict[str, Any]:
        use_gridmap = bool(args.get("use_gridmap", self.use_gridmap))
        return {
            "ok": True,
            "use_gridmap": use_gridmap,
            "save_path": f"{self.finish_root}/{self.date}",
            "save_path_temp": f"{self.finish_root}/{self.date}_temp",
            "trajectory_outputs": [
                f"{self.finish_root}/{self.date}/{segment}/{clip}/{clip}_trajectory.json"
                for segment, clip in zip(self.clip_segments, self.clip_names)
            ],
            "moved_final_result_paths": [
                f"{self.finish_root}/{self.date}/{segment}/{clip}"
                for segment, clip in zip(self.clip_segments, self.clip_names)
            ],
        }

    def _validate_outputs(self, args: dict[str, Any]) -> dict[str, Any]:
        return {
            "ok": True,
            "date": str(args.get("date") or self.date),
            "level": str(args.get("level") or "full"),
            "summary": "Validation passed for clip, annotation, tracking, and final outputs.",
            "missing": [],
        }


class FakeVLASessionAgent(DJSessionAgent):
    """DJSessionAgent with only fake VLA tools registered."""

    def __init__(
        self,
        *,
        fake_state: FakeVLAToolState,
        max_iters: int,
        **kwargs: Any,
    ) -> None:
        self.fake_state = fake_state
        self.fake_max_iters = max_iters
        super().__init__(**kwargs)

    def _build_toolkit(self):
        from agentscope.tool import Toolkit

        toolkit = Toolkit()
        for tool_name in DEFAULT_EXPECTED_CHAIN:
            spec = VLA_SPEC_BY_NAME[tool_name]
            func = self._fake_tool_function(spec)
            toolkit.register_tool_function(
                func,
                json_schema=build_agentscope_json_schema(spec),
            )
        return toolkit

    def _fake_tool_function(self, spec: ToolSpec):
        def _wrapped(**kwargs: Any):
            payload = self.fake_state.result_for(spec.name, dict(kwargs))
            return to_text_response(payload)

        _wrapped.__name__ = spec.name
        _wrapped.__doc__ = f"[FAKE] {spec.description}"
        return _wrapped

    def _build_react_agent(self):
        from agentscope.agent import ReActAgent
        from agentscope.formatter import OpenAIChatFormatter
        from agentscope.model import OpenAIChatModel

        api_key = self._api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("MODELSCOPE_API_TOKEN")
        if not api_key:
            raise RuntimeError("Missing API key: set DASHSCOPE_API_KEY or MODELSCOPE_API_TOKEN")

        base_url = self._base_url or os.environ.get(
            "DJA_OPENAI_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        thinking_flag = (
            os.environ.get("DJA_LLM_THINKING", "true").lower()
            in {"1", "true", "yes", "on"}
            if self._thinking is None
            else bool(self._thinking)
        )
        model_name = self._model_name or os.environ.get(
            "DJA_SESSION_MODEL",
            "qwen3-max-2026-01-23",
        )

        model = OpenAIChatModel(
            model_name=model_name,
            api_key=api_key,
            stream=self._enable_streaming,
            client_kwargs={"base_url": base_url},
            generate_kwargs={
                "temperature": 0,
                "extra_body": {"enable_thinking": thinking_flag},
            },
        )
        agent = ReActAgent(
            name="FakeVLASessionReActAgent",
            sys_prompt=self._session_sys_prompt(),
            model=model,
            formatter=OpenAIChatFormatter(),
            toolkit=self._build_toolkit(),
            max_iters=self.fake_max_iters,
            parallel_tool_calls=False,
        )
        self._register_react_hooks(agent)
        agent.set_console_output_enabled(enabled=self.verbose)
        return agent


def _list_arg(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _is_subsequence(expected: list[str], actual: list[str]) -> bool:
    index = 0
    for name in actual:
        if index < len(expected) and name == expected[index]:
            index += 1
    return index == len(expected)


def _first_order_violation(expected: list[str], actual: list[str]) -> str | None:
    positions: dict[str, int] = {}
    for idx, name in enumerate(actual):
        positions.setdefault(name, idx)
    missing = [name for name in expected if name not in positions]
    if missing:
        return "missing expected tool(s): " + ", ".join(missing)
    for before, after in zip(expected, expected[1:]):
        if positions[before] > positions[after]:
            return f"tool order violation: {before} appeared after {after}"
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a real LLM ReAct VLA orchestration smoke test with fake tool results.",
    )
    parser.add_argument("--date", default=os.environ.get("VLA_TEST_DATE", "20270515"))
    parser.add_argument(
        "--raw-segments",
        default=os.environ.get("VLA_TEST_RAW_SEGMENTS", "20260515_102948,20260515_103111"),
        help="Comma-separated raw segment names.",
    )
    parser.add_argument(
        "--clip-segments",
        default=os.environ.get("VLA_TEST_CLIP_SEGMENTS", ""),
        help="Comma-separated clip segment names. Defaults to raw segments.",
    )
    parser.add_argument("--scene-mode", default=os.environ.get("VLA_TEST_SCENE_MODE", "out"))
    parser.add_argument("--model", default=os.environ.get("DJA_SESSION_MODEL"))
    parser.add_argument("--base-url", default=os.environ.get("DJA_OPENAI_BASE_URL"))
    parser.add_argument("--api-key", default=None, help="Optional API key. Defaults to DASHSCOPE_API_KEY/MODELSCOPE_API_TOKEN.")
    parser.add_argument("--working-dir", default="./.djx/session")
    parser.add_argument("--max-iters", type=int, default=24)
    parser.add_argument("--strict", action="store_true", help="Exit 1 unless all expected tools are called in order.")
    parser.add_argument("--json-output", default="", help="Optional path to save the full smoke result JSON.")
    parser.add_argument(
        "--message",
        default="",
        help="Override the user message sent to the ReAct agent.",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--use-gridmap", action="store_true")
    parser.add_argument(
        "--no-thinking",
        action="store_true",
        help="Disable model thinking via AgentScope OpenAIChatModel extra_body.",
    )
    return parser.parse_args()


async def _main_async() -> int:
    args = _parse_args()
    raw_segments = _list_arg(args.raw_segments)
    clip_segments = _list_arg(args.clip_segments) or list(raw_segments)
    if not raw_segments:
        print("raw segments must not be empty", file=sys.stderr)
        return 2

    fake_state = FakeVLAToolState(
        date=str(args.date),
        raw_segments=raw_segments,
        clip_segments=clip_segments,
        scene_mode=str(args.scene_mode),
        use_gridmap=bool(args.use_gridmap),
    )
    message = args.message or (
        f"请处理 {args.date} 的导航 VLA 数据。"
        f"raw segments 是 {', '.join(raw_segments)}，"
        f"clip segments 是 {', '.join(clip_segments)}，"
        f"scene_mode={args.scene_mode}。"
        "请使用结构化 VLA 工具按默认链路推进，不要使用 shell 或 Python 执行工具。"
    )

    events: list[dict[str, Any]] = []

    def on_event(event: dict[str, Any]) -> None:
        events.append(event)

    agent = FakeVLASessionAgent(
        fake_state=fake_state,
        max_iters=int(args.max_iters),
        use_llm_router=True,
        working_dir=args.working_dir,
        verbose=bool(args.verbose),
        api_key=args.api_key,
        base_url=args.base_url,
        model_name=args.model,
        thinking=False if args.no_thinking else None,
        event_callback=on_event,
    )
    reply = await agent.handle_message_async(message)
    actual_chain = [call.name for call in fake_state.calls]
    order_error = _first_order_violation(DEFAULT_EXPECTED_CHAIN, actual_chain)
    pass_strict = order_error is None and _is_subsequence(DEFAULT_EXPECTED_CHAIN, actual_chain)

    report = {
        "ok": pass_strict,
        "strict": bool(args.strict),
        "date": args.date,
        "message": message,
        "expected_chain": DEFAULT_EXPECTED_CHAIN,
        "actual_chain": actual_chain,
        "order_error": order_error,
        "assistant_reply": reply.text,
        "tool_calls": [
            {
                "index": idx,
                "name": call.name,
                "args": call.args,
                "result_preview": call.result,
            }
            for idx, call in enumerate(fake_state.calls, start=1)
        ],
        "event_count": len(events),
    }

    print("\n== assistant reply ==")
    print(reply.text.strip() or "<empty>")
    print("\n== expected chain ==")
    print(" -> ".join(DEFAULT_EXPECTED_CHAIN))
    print("\n== actual chain ==")
    print(" -> ".join(actual_chain) if actual_chain else "<no tool calls>")
    print("\n== verdict ==")
    if pass_strict:
        print("PASS: expected VLA tool chain was called in order.")
    else:
        print(f"FAIL: {order_error or 'expected chain was not completed'}")

    print("\n== tool call args ==")
    for idx, call in enumerate(fake_state.calls, start=1):
        print(f"{idx:02d}. {call.name}: {json.dumps(call.args, ensure_ascii=False)}")

    if args.json_output:
        path = Path(args.json_output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nSaved JSON report: {path}")

    return 0 if (pass_strict or not args.strict) else 1


def main() -> int:
    return asyncio.run(_main_async())


if __name__ == "__main__":
    raise SystemExit(main())

from data_juicer_agents.capabilities.session.toolkit import get_session_tool_specs
from data_juicer_agents.core.tool import list_tool_specs


def test_vla_tools_are_auto_discovered():
    names = {spec.name for spec in list_tool_specs()}

    assert "vla_run_workflow" in names
    assert "vla_check_runtime" in names
    assert "vla_extract_and_sync" in names
    assert "vla_run_manual_box_annotation" in names
    assert "vla_validate_outputs" in names


def test_session_toolkit_prioritizes_structured_vla_workflow_tool():
    names = [spec.name for spec in get_session_tool_specs()]

    assert names.index("vla_run_workflow") < names.index("vla_check_runtime")
    assert names.index("vla_run_workflow") < names.index("vla_extract_and_sync")


def test_session_toolkit_orders_vla_before_generic_process_tools():
    names = [spec.name for spec in get_session_tool_specs()]

    assert names.index("vla_check_runtime") < names.index("execute_shell_command")


def test_session_prompt_mentions_vla_runtime_and_manual_annotation():
    from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

    agent = DJSessionAgent(use_llm_router=False)
    prompt = agent._session_sys_prompt()

    assert "vla_check_runtime" in prompt
    assert "vla_run_manual_box_annotation" in prompt
    assert "Python 3.8" in prompt
    assert "gen_box.py" in prompt


def test_session_prompt_allows_structured_vla_tools_to_use_configured_roots():
    from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

    agent = DJSessionAgent(use_llm_router=False)
    prompt = agent._session_sys_prompt()

    assert "structured VLA tools may operate on configured VLA roots" in prompt
    assert "raw_root, clip_root, finish_root, trajectory_root" in prompt
    assert "generic shell and file tools remain limited to the current working directory" in prompt


def test_session_prompt_tells_vla_tools_not_to_guess_runtime_paths():
    from data_juicer_agents.capabilities.session.orchestrator import DJSessionAgent

    agent = DJSessionAgent(use_llm_router=False)
    prompt = agent._session_sys_prompt()

    assert "never invent data_env_setup, data_python, data_toolbox_src, or root paths" in prompt
    assert "omit those arguments and let tool defaults resolve them from environment variables" in prompt

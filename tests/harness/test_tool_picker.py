# [阶段4] ToolPicker 脚本化与 LLM 解析

import asyncio
from unittest.mock import AsyncMock, patch

from app.harness.orchestration.tool_picker import (
    LlmToolPicker,
    ScriptedToolPicker,
    _parse_pick_json,
    build_tool_picker,
)
from app.harness.tools.registry import build_harness_registry
from app.harness.types.context import DatasetRef, RuntimeContext
from app.harness.types.explorer_state import ExplorerState
from app.harness.types.observation import Observation


def _ctx_with_ds() -> RuntimeContext:
    return RuntimeContext(
        run_id="r1",
        thread_id="t1",
        agent_id=1,
        user_query="销售额",
        mode="smart_query",
        datasets=[
            DatasetRef(
                datasource_id=1,
                datasource_name="ds",
                database_name="db",
                table_name="t",
            )
        ],
    )


def test_parse_pick_json_call_tool():
    d = _parse_pick_json(
        '{"action":"call_tool","tool":"inspect_schema","reasoning":"x"}',
        allowed={"inspect_schema", "search_knowledge"},
    )
    assert d is not None
    assert d.kind == "tool"
    assert d.tool_name == "inspect_schema"


def test_scripted_picker_first_step_is_search():
    async def _run():
        picker = ScriptedToolPicker()
        ctx = _ctx_with_ds()
        reg = build_harness_registry()
        decision = await picker.pick(
            ctx=ctx,
            observations=[],
            state=ExplorerState.from_context(ctx),
            registry=reg,
        )
        return decision

    decision = asyncio.run(_run())
    assert decision.kind == "tool"
    assert decision.tool_name == "search_knowledge"


def test_build_tool_picker_scripted_by_default():
    with patch("app.harness.orchestration.tool_picker.settings") as st:
        st.harness_v2_llm_tool_pick = False
        assert isinstance(build_tool_picker(), ScriptedToolPicker)


def test_llm_picker_fallback_on_bad_json():
    async def _run():
        picker = LlmToolPicker()
        ctx = _ctx_with_ds()
        reg = build_harness_registry()
        with patch(
            "app.harness.orchestration.tool_picker.llm_service.chat",
            new_callable=AsyncMock,
        ) as chat:
            chat.return_value = "not json"
            decision = await picker.pick(
                ctx=ctx,
                observations=[],
                state=ExplorerState.from_context(ctx),
                registry=reg,
            )
        return decision

    decision = asyncio.run(_run())
    assert decision.kind == "tool"
    assert decision.tool_name == "search_knowledge"


def test_scripted_finish_after_execute_ok():
    async def _run():
        picker = ScriptedToolPicker()
        ctx = _ctx_with_ds()
        reg = build_harness_registry()
        obs = [
            Observation(
                tool_name="execute_sql",
                status="ok",
                summary="ok",
            )
        ]
        decision = await picker.pick(
            ctx=ctx,
            observations=obs,
            state=ExplorerState.from_context(ctx),
            registry=reg,
        )
        return decision

    decision = asyncio.run(_run())
    assert decision.kind == "finish"

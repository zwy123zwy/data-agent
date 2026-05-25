# [阶段4] Tool 选择策略：脚本化（M4.0）与 LLM（M4.1）

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

from app.core.config import settings
from app.core.llm import llm_service
from app.harness.prompts import HarnessPromptKey, get_system_prompt_sync
from app.harness.tools.registry import ToolRegistry
from app.harness.types.context import RuntimeContext
from app.harness.types.explorer_state import ExplorerState
from app.harness.types.observation import Observation
from app.harness.types.tool_descriptor import ToolDescriptor

logger = logging.getLogger(__name__)

PickKind = Literal["tool", "finish"]


@dataclass(frozen=True)
class PickDecision:
    """[阶段4] 下一步：调用某 Tool 或结束循环进入 Answer。"""

    kind: PickKind
    tool_name: str | None = None
    reasoning: str = ""


def _max_sql_attempts() -> int:
    return max(1, int(getattr(settings, "harness_max_sql_attempts", 3)))


def _obs_tool_done(observations: list[Observation], tool_name: str) -> bool:
    return any(o.tool_name == tool_name for o in observations)


class ToolPicker(ABC):
    """[阶段4] 根据上下文选择下一步 Tool。"""

    @abstractmethod
    async def pick(
        self,
        *,
        ctx: RuntimeContext,
        observations: list[Observation],
        state: ExplorerState,
        registry: ToolRegistry,
    ) -> PickDecision:
        """[阶段4] 返回 tool 或 finish。"""


class ScriptedToolPicker(ToolPicker):
    """[阶段4] 固定策略：知识 → Schema → generate_sql ⇄ execute_sql。"""

    _PRE_TOOLS: tuple[str, ...] = ("search_knowledge", "inspect_schema")

    async def pick(
        self,
        *,
        ctx: RuntimeContext,
        observations: list[Observation],
        state: ExplorerState,
        registry: ToolRegistry,
    ) -> PickDecision:
        available = {d.name for d in registry.list_descriptors(ctx)}

        if observations:
            last = observations[-1]
            if last.tool_name == "execute_sql" and last.status == "ok":
                return PickDecision(kind="finish", reasoning="SQL 已成功执行")

        for name in self._PRE_TOOLS:
            if name not in available:
                continue
            if not _obs_tool_done(observations, name):
                return PickDecision(kind="tool", tool_name=name, reasoning="脚本化前置链")

        max_sql = _max_sql_attempts()
        gen_count = sum(1 for o in observations if o.tool_name == "generate_sql")

        if observations:
            last = observations[-1]
            if last.tool_name == "generate_sql" and last.status == "ok":
                if "execute_sql" in available:
                    return PickDecision(
                        kind="tool",
                        tool_name="execute_sql",
                        reasoning="执行已生成 SQL",
                    )
            if last.tool_name == "execute_sql" and last.status == "error":
                if (
                    last.error_severity == "retryable"
                    and gen_count < max_sql
                    and "generate_sql" in available
                ):
                    return PickDecision(
                        kind="tool",
                        tool_name="generate_sql",
                        reasoning="SQL 失败可重试",
                    )

        if gen_count < max_sql and "generate_sql" in available:
            return PickDecision(kind="tool", tool_name="generate_sql", reasoning="生成 SQL")

        if state.has_sql_result():
            return PickDecision(kind="finish", reasoning="已有查询结果")
        return PickDecision(kind="finish", reasoning="SQL 链路未成功")


class LlmToolPicker(ToolPicker):
    """[阶段4] LLM 按 ToolDescriptor 选步；解析失败时回退 ScriptedToolPicker。"""

    def __init__(self) -> None:
        self._fallback = ScriptedToolPicker()

    async def pick(
        self,
        *,
        ctx: RuntimeContext,
        observations: list[Observation],
        state: ExplorerState,
        registry: ToolRegistry,
    ) -> PickDecision:
        descriptors = registry.list_descriptors(ctx)
        if not descriptors:
            return PickDecision(kind="finish", reasoning="无可用工具")

        decision = await self._llm_pick(ctx, observations, descriptors)
        if decision is not None:
            return decision

        logger.warning("[阶段4][LlmToolPicker] LLM 解析失败，回退脚本化策略")
        return await self._fallback.pick(
            ctx=ctx,
            observations=observations,
            state=state,
            registry=registry,
        )

    async def _llm_pick(
        self,
        ctx: RuntimeContext,
        observations: list[Observation],
        descriptors: list[ToolDescriptor],
    ) -> PickDecision | None:
        tools_block = "\n".join(
            f"- {d.name}: {d.description} ({d.constraints_summary})" for d in descriptors
        )
        obs_block = (
            "\n".join(
                f"- {o.tool_name} [{o.status}]: {o.summary[:300]}"
                for o in observations[-8:]
            )
            or "（尚无观察）"
        )
        user_prompt = (
            f"用户问题: {ctx.user_query}\n\n"
            f"可用工具:\n{tools_block}\n\n"
            f"已有观察:\n{obs_block}\n"
        )
        system_prompt = get_system_prompt_sync(
            HarnessPromptKey.TOOL_PICKER,
            overrides=ctx.prompt_overrides,
        )
        try:
            raw = await llm_service.chat(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
            )
        except Exception as exc:
            logger.warning("[阶段4][LlmToolPicker] LLM 调用失败: %s", exc)
            return None

        return _parse_pick_json(raw, allowed={d.name for d in descriptors})


def _parse_pick_json(raw: str, *, allowed: set[str]) -> PickDecision | None:
    """[阶段4] 解析 LLM 输出的选步 JSON。"""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]*\"action\"[^{}]*\}", text)
        if not match:
            return None
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return None

    action = str(data.get("action", "")).strip().lower()
    reasoning = str(data.get("reasoning", "")).strip()
    if action == "finish":
        return PickDecision(kind="finish", reasoning=reasoning or "LLM 判定可结束")

    if action != "call_tool":
        return None
    tool = str(data.get("tool") or "").strip()
    if tool not in allowed:
        return None
    return PickDecision(kind="tool", tool_name=tool, reasoning=reasoning)


def build_tool_picker() -> ToolPicker:
    """[阶段4] 按配置创建选步策略。"""
    if getattr(settings, "harness_v2_llm_tool_pick", False):
        return LlmToolPicker()
    return ScriptedToolPicker()

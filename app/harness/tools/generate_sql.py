# [阶段2] generate_sql — LLM + state schema，无 workflows 节点包装
# [Harness: Tool Access #1] SQL 生成工具，基于 Schema + 知识证据生成 SELECT 语句。
#
# 两条 prompt 路径:
#   ① 新生成 (regenerate 为 None): 注入 dialect + schema + knowledge + user_query
#   ② 修正生成 (regenerate 存在): 注入上次 SQL + 错误类型 + 错误原因
#      修正路径由 execute_sql 失败后设置 state["sql_regenerate_reason"] 触发，
#      explorer 重试循环会在下一次 generate_sql 调用时走此路径。
#      重试上限由 Explorer 统一控制（M2.5 已移除本工具内独立上限）。

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.harness.tools.base import BaseTool, ToolResult
from app.harness.types.artifacts import Artifact, Provenance
from app.harness.types.context import RuntimeContext
from app.core.llm import llm_service
from app.core.text_utils import clean_code_block
from app.harness.tools.constants import NL2SQL_INSTRUCTION, NL2SQL_PLAN_JSON

logger = logging.getLogger(__name__)

_SQL_SYSTEM = """你是 SQL 专家。只返回 SELECT 语句，不要解释。禁止写操作。"""


class HarnessGenerateSqlTool(BaseTool):
    """[阶段2] 基于 schema 与知识证据生成 SQL。"""

    name = "generate_sql"

    async def run(
        self,
        ctx: RuntimeContext,
        state: dict[str, Any],
        db: AsyncSession,
    ) -> ToolResult:
        state.setdefault("query_plan", NL2SQL_PLAN_JSON)
        state.setdefault("plan_current_step", 1)
        schema = state.get("schema") or ""
        if not schema:
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary="无 Schema，请先执行 inspect_schema",
                error_code="NO_SCHEMA",
                error_severity="fatal",
            )

        dialect = state.get("db_dialect_type") or (ctx.datasets[0].dialect if ctx.datasets else "mysql")
        evidence = state.get("recalled_knowledge", "")
        regenerate = state.get("sql_regenerate_reason")
        gen_count = int(state.get("sql_generate_count", 0))

        if regenerate:
            last_sql = state.get("generated_sql", "")
            reason = regenerate.get("reason", str(regenerate))
            err_type = regenerate.get("type", "unknown")
            prompt = (
                f"上次 SQL:\n{last_sql}\n\n错误类型: {err_type}\n错误: {reason}\n\n"
                f"步骤需求: {NL2SQL_INSTRUCTION}\n请修正后只返回 SQL。"
            )
        else:
            # TODO(H2): prompt 未包含多轮上下文 (multi_turn_context 恒为 "")。
            #   H2 后需注入历史轮次，帮助 LLM 理解"和上次比"、"环比"等追问语义。
            # 答：对。state["multi_turn_context"] 来自 explorer，H2 应从 ctx.memory 格式化写入；
            #   追问类 query 强烈依赖此项，否则每轮 SQL 仅看当前 user_query。
            prompt = (
                f"数据库方言: {dialect}\n\nSchema:\n{schema}\n\n"
                f"知识证据:\n{evidence}\n\n用户问题: {ctx.user_query}\n\n"
                f"步骤需求: {NL2SQL_INSTRUCTION}\n请生成 SQL。"
            )

        try:
            raw = await llm_service.chat(_SQL_SYSTEM, prompt, temperature=0.0)
            sql = clean_code_block(raw, lang="sql")
        except Exception as exc:
            logger.error("[阶段2][generate_sql] %s", exc)
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary=str(exc)[:200],
                error_code="SQL_GENERATE_ERROR",
                error_severity="retryable",
            )

        if not sql.strip():
            return ToolResult(
                status="error",
                tool_name=self.name,
                summary="SQL 生成为空",
                error_code="SQL_GENERATE_EMPTY",
                error_severity="retryable",
            )

        state["generated_sql"] = sql
        state["sql_generate_count"] = gen_count + 1
        state["sql_regenerate_reason"] = None

        obs_id = str(uuid4())
        artifact = Artifact(
            type="sql",
            content=sql,
            provenance=Provenance(
                agent_name="Explorer",
                tool_name=self.name,
                observation_id=obs_id,
            ),
        )
        return ToolResult(
            status="ok",
            tool_name=self.name,
            data={"sql": sql},
            summary=artifact.summary(80),
            artifacts=[artifact],
            v1_text=sql,
            v1_text_type="SQL",
        )

# [阶段4] ConstraintRunner — 工具执行前后权限与策略校验（M4.0 最小集）

from __future__ import annotations

from dataclasses import dataclass

from app.harness.tools.base import ToolResult
from app.harness.types.context import RuntimeContext


@dataclass(frozen=True)
class ConstraintBlock:
    """[阶段4] 约束拦截原因。"""

    code: str
    summary: str


class ConstraintRunner:
    """[阶段4] 按 Tool 名与 ctx.permissions 执行前后检查。"""

    def run_before(
        self,
        tool_name: str,
        ctx: RuntimeContext,
        *,
        step_index: int = 0,
    ) -> ConstraintBlock | None:
        """[阶段4] 执行前校验；返回 ConstraintBlock 表示禁止执行。"""
        _ = step_index
        if tool_name == "execute_sql" and not ctx.permissions.allow_write_operations:
            # M4.0：只读问数默认允许 SELECT；写操作需显式开启
            pass
        if tool_name in ("generate_sql", "execute_sql", "inspect_schema", "search_knowledge"):
            if not ctx.datasets:
                return ConstraintBlock(
                    code="NO_DATASOURCE",
                    summary="当前 Agent 未配置数据源，无法执行库表相关工具",
                )
        return None

    def run_after(
        self,
        tool_name: str,
        ctx: RuntimeContext,
        result: ToolResult,
    ) -> ToolResult:
        """[阶段4] 执行后处理；M4.0 原样返回。"""
        _ = tool_name, ctx
        return result

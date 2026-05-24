# [阶段2] Harness ToolRegistry — 无 wrap_v1 / V1NodeTool
# [Harness: Tool Access #1] 内存注册表，管理所有可用 Tool 的注册和查找。
#
# 当前注册的 4 个 Tool 构成 smart_query 完整链路:
#   search_knowledge → inspect_schema → generate_sql → execute_sql
# build_harness_registry() 每次调用创建新实例（无状态共享，适合每次 Run 独立执行）。
#
# list_for_mode(): 按 mode 返回工具名列表，供 mode_runner 发 tools.available SSE 事件。
#   当前仅 smart_query 有工具，deep_research/report 返回空列表（未实现）。

from __future__ import annotations

from app.harness.tools.base import BaseTool
from app.harness.tools.execute_sql import HarnessExecuteSqlTool
from app.harness.tools.generate_sql import HarnessGenerateSqlTool
from app.harness.tools.inspect_schema import HarnessInspectSchemaTool
from app.harness.tools.search_knowledge import HarnessSearchKnowledgeTool


class ToolRegistry:
    """[阶段2] Harness 内存 Tool 注册表。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())


def build_harness_registry() -> ToolRegistry:
    """[阶段2] smart_query 核心四 Tool。"""
    registry = ToolRegistry()
    for tool in (
        HarnessSearchKnowledgeTool(),
        HarnessInspectSchemaTool(),
        HarnessGenerateSqlTool(),
        HarnessExecuteSqlTool(),
    ):
        registry.register(tool)
    return registry


# [阶段2] 能力清单（非执行计划）：供 mode_runner 发 tools.available。
# 多次 SQL：A 失败重试见 explorer；B 多表多步见 Phase 4 Planner（见 OpenSpec TOOL-REGISTRY 文档）
def list_for_mode(mode: str) -> list[str]:
    """[阶段2] 按 mode 返回 Tool 类型名（T-06）；不表示调用次数。"""
    if mode == "smart_query":
        return ["search_knowledge", "inspect_schema", "generate_sql", "execute_sql"]
    return []

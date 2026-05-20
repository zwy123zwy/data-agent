# [阶段1] ToolRegistry — 注册与按名获取 V2 Tool

from __future__ import annotations

from app.agent_runtime.tools.base import BaseTool


class ToolRegistry:
    """[阶段1] 内存 Tool 注册表；阶段 2 扩展为 12 Tool 全量注册。"""

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


def build_full_registry() -> ToolRegistry:
    """[阶段2] 12 Tool 全量注册。"""
    from app.agent_runtime.tools.build_registry import build_full_registry as _full

    return _full()


def build_phase1_registry() -> ToolRegistry:
    """[阶段1] smart_query 最小闭环：3 个 Tool。"""
    from app.agent_runtime.tools.search_knowledge import SearchKnowledgeTool
    from app.agent_runtime.tools.generate_sql import GenerateSqlTool
    from app.agent_runtime.tools.execute_sql import ExecuteSqlTool

    registry = ToolRegistry()
    registry.register(SearchKnowledgeTool())
    registry.register(GenerateSqlTool())
    registry.register(ExecuteSqlTool())
    return registry

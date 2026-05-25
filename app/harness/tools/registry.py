# [阶段4] Harness ToolRegistry — ToolDescriptor 单源
# [Harness: Tool Access #1]

from __future__ import annotations

from app.harness.tools.base import BaseTool
from app.harness.tools.execute_sql import HarnessExecuteSqlTool
from app.harness.tools.generate_sql import HarnessGenerateSqlTool
from app.harness.tools.inspect_schema import HarnessInspectSchemaTool
from app.harness.tools.search_knowledge import HarnessSearchKnowledgeTool
from app.harness.types.context import RuntimeContext
from app.harness.types.tool_descriptor import ToolDescriptor

# [阶段4] 内置 Tool 元数据（M4.1 可下沉到各 Tool.descriptor()）
_BUILTIN_DESCRIPTORS: tuple[ToolDescriptor, ...] = (
    ToolDescriptor(
        name="search_knowledge",
        description="检索业务术语与 Agent 知识，改写查询后向量召回",
        constraints_summary="只读检索；失败可降级",
        requires_datasource=True,
    ),
    ToolDescriptor(
        name="inspect_schema",
        description="拉取数据源表结构 DDL，供 NL2SQL 使用",
        constraints_summary="只读 Schema",
        requires_datasource=True,
    ),
    ToolDescriptor(
        name="generate_sql",
        description="根据 Schema 与知识生成 SELECT 语句",
        constraints_summary="仅生成 SQL，不执行",
        requires_datasource=True,
    ),
    ToolDescriptor(
        name="execute_sql",
        description="校验并执行 SQL，受行数上限与超时约束",
        constraints_summary="只读 SQL 校验；max_sql_result_rows",
        requires_datasource=True,
    ),
    ToolDescriptor(
        name="parse_file",
        description="解析会话上传文件为结构化摘要（M3 实现）",
        constraints_summary="仅当会话含附件时可用",
        requires_files=True,
    ),
)


class ToolRegistry:
    """[阶段2] Harness 内存 Tool 注册表。"""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._descriptors: dict[str, ToolDescriptor] = {}

    def register(self, tool: BaseTool, *, descriptor: ToolDescriptor | None = None) -> None:
        self._tools[tool.name] = tool
        if descriptor is not None:
            self._descriptors[tool.name] = descriptor

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise KeyError(f"Tool not registered: {name}")
        return self._tools[name]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def list_descriptors(self, ctx: RuntimeContext) -> list[ToolDescriptor]:
        """[阶段4] 按 RuntimeContext 过滤可用 Tool 元数据。"""
        has_ds = bool(ctx.datasets)
        has_files = bool(ctx.file_refs)
        out: list[ToolDescriptor] = []
        for desc in self._descriptors.values():
            if desc.requires_datasource and not has_ds:
                continue
            if desc.requires_files and not has_files:
                continue
            if desc.name not in self._tools:
                continue
            out.append(desc)
        return sorted(out, key=lambda d: d.name)


def build_harness_registry() -> ToolRegistry:
    """[阶段2] smart_query 核心四 Tool + parse_file 占位描述（M3 注册实现）。"""
    registry = ToolRegistry()
    tool_instances = (
        HarnessSearchKnowledgeTool(),
        HarnessInspectSchemaTool(),
        HarnessGenerateSqlTool(),
        HarnessExecuteSqlTool(),
    )
    desc_by_name = {d.name: d for d in _BUILTIN_DESCRIPTORS}
    for tool in tool_instances:
        registry.register(tool, descriptor=desc_by_name.get(tool.name))
    return registry


def list_descriptors(ctx: RuntimeContext) -> list[ToolDescriptor]:
    """[阶段4] 便捷方法：构建注册表并返回当前 Run 可用 descriptors。"""
    return build_harness_registry().list_descriptors(ctx)

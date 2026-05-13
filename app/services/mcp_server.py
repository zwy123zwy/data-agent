"""
MCP (Model Context Protocol) Server 服务 — 对齐 Java McpServerService
提供 NL2SQL Tool + ListAgents Tool，用于 Claude Desktop 集成
"""
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class McpToolResult:
    """MCP Tool 执行结果"""

    def __init__(self, content: List[Dict[str, Any]], is_error: bool = False):
        self.content = content
        self.is_error = is_error


class McpServerService:
    """MCP Server 服务 — 对齐 Java McpServerService

    提供两个 Tool:
    1. nl2sql — 自然语言转 SQL
    2. list_agents — 列出所有 Agent
    """

    def __init__(self):
        self.tools = [
            {
                "name": "nl2sql",
                "description": "将自然语言查询转换为 SQL 语句并执行，返回查询结果",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "用户的自然语言查询",
                        },
                        "agent_id": {
                            "type": "integer",
                            "description": "Agent ID，用于确定数据源",
                        },
                    },
                    "required": ["query", "agent_id"],
                },
            },
            {
                "name": "list_agents",
                "description": "列出所有可用的 Data Agent 及其配置信息",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def get_tools(self) -> List[Dict[str, Any]]:
        """获取 Tool 定义列表"""
        return self.tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> McpToolResult:
        """调用 Tool — 对齐 Java McpServerService

        Args:
            tool_name: Tool 名称
            arguments: Tool 参数

        Returns:
            McpToolResult
        """
        if tool_name == "nl2sql":
            return await self._nl2sql_tool(arguments)
        elif tool_name == "list_agents":
            return await self._list_agents_tool()
        else:
            return McpToolResult(
                content=[{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                is_error=True,
            )

    async def _nl2sql_tool(self, arguments: Dict[str, Any]) -> McpToolResult:
        """NL2SQL Tool — 对齐 Java nl2SqlToolCallback"""
        query = arguments.get("query", "")
        agent_id = arguments.get("agent_id")

        if not query:
            return McpToolResult(
                content=[{"type": "text", "text": "Error: query is required"}],
                is_error=True,
            )

        if not agent_id:
            return McpToolResult(
                content=[{"type": "text", "text": "Error: agent_id is required"}],
                is_error=True,
            )

        try:
            from ..workflows.graph import get_compiled_workflow

            initial_state = {
                "agent_id": agent_id,
                "user_query": query,
                "is_only_nl2sql": True,
                "sql_retry_count": 0,
                "sql_generate_count": 0,
                "plan_current_step": 1,
            }

            compiled_workflow = await get_compiled_workflow()
            result = await compiled_workflow.ainvoke(initial_state)

            sql = result.get("generated_sql", "")
            sql_result = result.get("sql_result")
            error = result.get("error") or result.get("sql_error")

            if error:
                return McpToolResult(
                    content=[{"type": "text", "text": f"Error: {error}"}],
                    is_error=True,
                )

            output = {
                "sql": sql,
                "result": sql_result,
                "row_count": len(sql_result) if sql_result else 0,
            }

            return McpToolResult(
                content=[{"type": "text", "text": json.dumps(output, ensure_ascii=False, indent=2)}],
            )

        except Exception as e:
            logger.error(f"[MCP] nl2sql error: {e}")
            return McpToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                is_error=True,
            )

    async def _list_agents_tool(self) -> McpToolResult:
        """ListAgents Tool — 对齐 Java listAgentsToolCallback"""
        try:
            from ..core.database import async_session_maker
            from ..services.agent_service import AgentService

            async with async_session_maker() as session:
                agents = await AgentService.list_agents(session)
                agent_list = [
                    {
                        "id": a.id,
                        "name": a.name,
                        "description": getattr(a, "description", ""),
                        "status": getattr(a, "status", "active"),
                    }
                    for a in agents
                ]

            return McpToolResult(
                content=[{
                    "type": "text",
                    "text": json.dumps(agent_list, ensure_ascii=False, indent=2),
                }],
            )

        except Exception as e:
            logger.error(f"[MCP] list_agents error: {e}")
            return McpToolResult(
                content=[{"type": "text", "text": f"Error: {str(e)}"}],
                is_error=True,
            )


# 全局实例
_mcp_server: Optional[McpServerService] = None


def get_mcp_server_service() -> McpServerService:
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = McpServerService()
    return _mcp_server

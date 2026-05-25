# [阶段1] Preflight 与 prompt_guard 数据结构
# [Harness: Sandbox #5 + Memory #4]
#
# PreflightSnapshot 是 PPAF 第一环的输出，被 downstream 各环节只读消费:
#   - coordinator: 检查 blocked 字段决定是否终止
#   - routing:      检查 has_datasource（及 agent 置信度）决定是否走 clarify
#   - builder:      读取 probe.datasets 和 probe.semantic_prompt 装配 RuntimeContext
#   - gateway:      通过 to_prompt_lines() 注入 LLM 分类 prompt 的环境摘要
#
# probe 字段: 一次 DB 探测结果缓存在快照中，避免 builder 重复查库。
#   类型为 DatasourceProbeSnapshot | None，当 agent 无效时为 None。

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.harness.types.datasource_probe import DatasourceProbeSnapshot


class PromptGuardResult(BaseModel):
    """[阶段1] 用户输入规则扫描结果。"""

    risk_level: Literal["ok", "warn", "block"] = "ok"
    code: str | None = None
    message: str = ""

    model_config = ConfigDict(extra="forbid")


class PreflightSnapshot(BaseModel):
    """[阶段1] ② 用户校验快照，供 Gateway/Planner 只读。"""

    agent_ok: bool = True
    agent_id: int = 0
    risk_level: Literal["ok", "warn", "block"] = "ok"
    blocked: bool = False
    block_code: str | None = None
    has_datasource: bool = False
    has_files: bool = False
    select_tables: list[str] = Field(default_factory=list)
    semantic_warn: bool = False
    nl2sql_only: bool = False
    # [阶段2] 一次探测结果，builder 只读（不出 SSE）
    probe: DatasourceProbeSnapshot | None = None

    model_config = ConfigDict(extra="forbid")

    def to_prompt_lines(self) -> list[str]:
        """[阶段1] 转为 Gateway user prompt 中的环境摘要行。"""
        lines = [
            f"- Agent 有效: {'是' if self.agent_ok else '否'}",
            f"- 有激活数据源: {'是' if self.has_datasource else '否'}",
            f"- 已选表: {', '.join(self.select_tables) if self.select_tables else '（无）'}",
            f"- 语义模型警告: {'是' if self.semantic_warn else '否'}",
            f"- 会话含文件: {'是' if self.has_files else '否'}",
        ]
        return lines

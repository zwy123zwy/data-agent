# [阶段2] 数据源探测快照 — Preflight 与 builder 共享
# [Harness: Memory #4]
#
# 职责: 一次 DB 探测，缓存结果供 preflight + builder 只读，避免重复查库。
# 包含: 激活数据源信息 + 已选表列表 + 语义模型片段 + 构造好的 DatasetRef 列表。
#
# semantic_warn: 前 5 张表中有表缺少语义模型时为 True，
#   在 Preflight.to_prompt_lines() 中提示 Gateway 注意。

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.harness.types.context import DatasetRef


class DatasourceProbeSnapshot(BaseModel):
    """[阶段2] 一次 DB 探测结果，避免 preflight/builder 重复查库。"""

    has_datasource: bool = False
    datasource_id: int | None = None
    dialect: str = "mysql"
    select_tables: list[str] = Field(default_factory=list)
    semantic_warn: bool = False
    semantic_prompt: str = ""
    datasets: list[DatasetRef] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

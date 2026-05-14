"""
表关系构建节点（Table Relation Node） — 对齐 Java TableRelationNode
基于外键 + 同名字段 + LLM 推理构建表间关系
"""
from typing import Dict, Any, List, Optional
from ..state import WorkflowState
from ...core.llm import llm_service
from ...core.text_utils import clean_code_block
from ...services.schema_service import SchemaService
from ...services.agent_datasource_service import AgentDatasourceService
from ...core.database import async_session_maker
from ...core.datasource_handler import get_handler
import logging
import json

logger = logging.getLogger(__name__)

TABLE_RELATION_SYSTEM_PROMPT = """你是一个数据库关系分析专家。
给定数据库的表结构信息，分析表之间可能存在的关系。

分析依据：
1. 外键关系（显式声明的 foreign key）
2. 同名字段（如两个表都有 user_id，很可能有关系）
3. 字段名语义相似度（如 customer_id 和 client_id）
4. 业务逻辑推断

返回 JSON 格式：
{
  "tables": [
    {
      "tableName": "users",
      "tableComment": "用户表",
      "columns": [
        {
          "columnName": "id",
          "columnType": "int",
          "columnComment": "用户ID",
          "isPrimaryKey": true,
          "isForeignKey": false
        }
      ],
      "foreignKeys": [
        {
          "columnName": "user_id",
          "referencedTable": "users",
          "referencedColumn": "id"
        }
      ]
    }
  ],
  "relations": [
    {
      "fromTable": "orders",
      "fromColumn": "user_id",
      "toTable": "users",
      "toColumn": "id",
      "type": "explicit_fk"
    }
  ]
}
"""


def _detect_implicit_relations(tables: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """检测隐式关系：同名字段 + 命名模式匹配"""
    relations = []
    col_index: Dict[str, List[tuple]] = {}

    for table in tables:
        for col in table.get("columns", []):
            col_name = col["name"].lower()
            if col_name not in col_index:
                col_index[col_name] = []
            col_index[col_name].append((table["name"], col["name"]))

    # 出现在多个表中的同名字段 → 潜在关系
    for col_name, occurrences in col_index.items():
        if len(occurrences) >= 2 and col_name not in ("id", "name", "created_at", "updated_at", "create_time", "update_time", "created_time", "updated_time", "status"):
            for i in range(len(occurrences)):
                for j in range(i + 1, len(occurrences)):
                    relations.append({
                        "fromTable": occurrences[i][0],
                        "fromColumn": occurrences[i][1],
                        "toTable": occurrences[j][0],
                        "toColumn": occurrences[j][1],
                        "type": "same_name"
                    })

    return relations


async def _llm_enhance_relations(
    schema_text: str, explicit_fks: List[Dict], implicit_rels: List[Dict]
) -> Dict[str, Any]:
    """LLM 增强关系推理"""
    try:
        prompt = (
            f"数据库 Schema:\n{schema_text}\n\n"
            f"已发现的外键关系:\n{json.dumps(explicit_fks, ensure_ascii=False, indent=2)}\n\n"
            f"已发现的同名字段关系:\n{json.dumps(implicit_rels, ensure_ascii=False, indent=2)}\n\n"
            f"请分析并返回完整的表关系 JSON。"
        )
        text = await llm_service.chat(TABLE_RELATION_SYSTEM_PROMPT, prompt, temperature=0.0)
        return json.loads(clean_code_block(text, lang="json"))
    except Exception as e:
        logger.warning(f"[TableRelation] LLM enhancement failed: {e}, using basic relations")
        return {}


async def table_relation_node(state: WorkflowState) -> Dict[str, Any]:
    """表关系构建节点 — 对齐 Java TableRelationNode.apply()"""
    agent_id = state["agent_id"]

    try:
        async with async_session_maker() as session:
            datasource = await AgentDatasourceService.get_active_datasource(session, agent_id)
            if not datasource:
                logger.error(f"[TableRelation] Agent {agent_id}: no active datasource")
                return {"error": "No active datasource", "table_relation_exception": "没有激活的数据源"}

            schema_data = await SchemaService.get_database_schema(datasource)
            tables = schema_data.get("tables", [])
            logger.info(f"[TableRelation] Processing {len(tables)} tables for agent {agent_id}")

            # 收集外键关系
            explicit_fks = []
            for table in tables:
                for fk in table.get("foreign_keys", []):
                    explicit_fks.append({
                        "fromTable": table["name"],
                        "fromColumn": fk["column_name"],
                        "toTable": fk["referenced_table"],
                        "toColumn": fk["referenced_column"],
                        "type": "explicit_fk"
                    })

            # 检测隐式关系
            implicit_rels = _detect_implicit_relations(tables)
            logger.info(f"[TableRelation] Found {len(explicit_fks)} explicit FKs, {len(implicit_rels)} implicit relations")

            # 构建 schema 文本
            schema_text = await SchemaService.get_database_ddl(datasource)

            # LLM 增强
            enhanced = await _llm_enhance_relations(schema_text, explicit_fks, implicit_rels)
            all_relations = enhanced.get("relations", explicit_fks + implicit_rels)
            enhanced_tables = enhanced.get("tables", tables)

            # 获取方言类型 (通过 Handler 策略模式)
            handler = get_handler(datasource.type)
            dialect = handler.dialect_type() if handler else datasource.type

            # 构建输出 SchemaDTO
            schema_dto = {
                "tables": enhanced_tables,
                "relations": all_relations,
                "dialect": dialect,
                "database": datasource.database_name,
            }

            return {
                "schema": schema_text,
                "schema_info": schema_dto,
                "db_dialect_type": dialect,
                "table_relation_exception": None,
            }

    except Exception as e:
        retry_count = state.get("table_relation_retry_count", 0)
        logger.error(f"[TableRelation] Error (retry {retry_count}): {e}")
        return {
            "table_relation_exception": str(e),
            "table_relation_retry_count": retry_count + 1,
        }

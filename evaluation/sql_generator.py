"""
SQL 生成器 — 评测用的独立 SQL 生成模块

【在系统中的地位】
  从主工作流中提取的轻量级 Text-to-SQL 生成能力。
  不依赖完整的 LangGraph 工作流 (无需 Agent/Datasource/知识库)，
  直接使用 Schema + NL 问题 + LLM 生成 SQL。

【模块连接】
  上游:
    - run_evaluation.py → 对每条 test_case 调用 generate_sql()

  依赖:
    - app/core/llm.py       → llm_service.chat() — LLM 调用
    - app/core/text_utils.py → clean_code_block() — 清洗 LLM 输出
    - datasets/*/schema.sql  → 表结构 (作为 prompt 的一部分)

  与本尊的区别:
    - workflows/nodes/sql_generate.py  ← 完整工作流中的 SQL 生成 (有重试/语义校验/错误恢复)
    - evaluation/sql_generator.py      ← 评测用的简化版 (直调 LLM，不含重试逻辑，便于独立评测)

  Java 对应:
    本模块 ≈ SqlGenerateNode.java 的核心 SQL 生成逻辑剥离版
"""
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.llm import llm_service
from app.core.text_utils import clean_code_block
import logging

logger = logging.getLogger(__name__)

# 评测专用 System Prompt — 比工作流版本更聚焦于评测指标
EVAL_SQL_SYSTEM_PROMPT = """你是一个 SQL 专家，需要根据数据库 Schema 和自然语言问题生成准确的 SQL 查询。

要求:
1. 只返回 SQL 语句，不要有任何解释、注释或 markdown 格式
2. 使用标准 SQL 语法，兼容 MySQL 方言
3. 表名和字段名严格使用 Schema 中定义的名称
4. 只生成 SELECT 语句，禁止 INSERT/UPDATE/DELETE/TRUNCATE/DROP
5. 注意 NULL 值处理 (使用 COALESCE 或 IS NULL)
6. JOIN 时注意 LEFT JOIN vs INNER JOIN 的选择
7. 聚合查询注意 GROUP BY 的完整性
"""


class SqlGenerator:
    """SQL 生成器 — 评测专用

    使用方式:
        gen = SqlGenerator(schema_sql="CREATE TABLE ...", dialect="mysql")
        sql = await gen.generate("查询所有用户")
    """

    def __init__(self, schema_sql: str = "", dialect: str = "mysql"):
        """
        Args:
            schema_sql: DDL 语句 (CREATE TABLE ...)
            dialect: 数据库方言 (mysql / postgresql / sqlite)
        """
        self.schema = schema_sql
        self.dialect = dialect

    async def generate(self, question: str, instruction: str = "") -> str:
        """根据自然语言问题生成 SQL

        Args:
            question: 自然语言问题
            instruction: 可选的额外指令 (来自 test_case 的 category/features)

        Returns:
            生成的 SQL 语句
        """
        prompt_parts = [
            f"数据库方言: {self.dialect}",
            "",
            f"数据库 Schema:",
            self.schema,
            "",
            f"用户问题: {question}",
        ]

        if instruction:
            prompt_parts.append(f"")
            prompt_parts.append(f"补充指令: {instruction}")

        user_prompt = "\n".join(prompt_parts)

        try:
            raw = await llm_service.chat(
                EVAL_SQL_SYSTEM_PROMPT,
                user_prompt,
                temperature=0.0
            )
            sql = clean_code_block(raw, lang="sql")
            logger.info(f"[SqlGenerator] Generated SQL ({len(sql)} chars): {sql[:120]}...")
            return sql
        except Exception as e:
            logger.error(f"[SqlGenerator] LLM call failed: {e}")
            raise


async def generate_sql_from_schema(
    question: str,
    schema_sql: str,
    dialect: str = "mysql",
    instruction: str = "",
) -> str:
    """便捷函数：根据 Schema 和问题生成 SQL

    Args:
        question: 自然语言问题
        schema_sql: 数据库 DDL
        dialect: 数据库方言
        instruction: 额外指令

    Returns:
        生成的 SQL 语句
    """
    generator = SqlGenerator(schema_sql, dialect)
    return await generator.generate(question, instruction)

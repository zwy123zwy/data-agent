from typing import TypedDict, Optional, List, Dict, Any


class WorkflowState(TypedDict, total=False):
    """工作流状态"""
    # 输入
    agent_id: int
    user_query: str

    # 意图识别
    intent: Optional[str]  # "chitchat" | "data_analysis"

    # 知识召回（Phase 2）
    recalled_knowledge: Optional[str]  # 召回的知识文本
    knowledge_items: Optional[List[Dict[str, Any]]]  # 知识项列表
    rewritten_query: Optional[str]  # 改写后的查询

    # 数据库 schema
    schema: Optional[str]  # LLM 使用的文本格式 DDL
    schema_info: Optional[Dict[str, Any]]  # 结构化的 schema 数据

    # 计划生成（Phase 2）
    is_complex_query: Optional[bool]  # 是否是复杂查询
    query_plan: Optional[Dict[str, Any]]  # 查询计划
    plan_execution_result: Optional[Dict[str, Any]]  # 计划执行结果

    # SQL 生成
    generated_sql: Optional[str]
    sql_retry_count: int

    # SQL 执行
    sql_result: Optional[List[Dict[str, Any]]]
    sql_error: Optional[str]

    # Python 分析（Phase 3）
    python_code: Optional[str]  # 生成的 Python 代码
    python_output: Optional[str]  # Python 执行输出
    python_error: Optional[str]  # Python 执行错误
    python_charts: Optional[List[str]]  # 生成的图表列表
    python_data: Optional[Any]  # Python 返回的数据
    python_analysis: Optional[str]  # Python 分析结论

    # 报告
    report: Optional[str]  # Markdown 报告
    html_report: Optional[str]  # HTML 报告
    markdown_report: Optional[str]  # Markdown 报告

    # 错误信息
    error: Optional[str]


# 别名，兼容旧代码
AgentState = WorkflowState

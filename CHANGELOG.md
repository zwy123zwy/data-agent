# 修改文件记录 (CHANGELOG)

## Phase 3: Python 分析与报告 (2024-04-26)

### 新增文件
1. `app/core/code_executor.py` - 代码执行器服务
2. `app/workflows/nodes/python_generate.py` - Python 代码生成节点
3. `app/workflows/nodes/python_execute.py` - Python 代码执行节点
4. `app/workflows/nodes/python_analyze.py` - Python 分析节点
5. `app/workflows/nodes/report_generator.py` - 报告生成节点
6. `docs/PHASE3_DESIGN.md` - Phase 3 技术设计
7. `PHASE3_COMPLETE.md` - Phase 3 完成报告

### 修改文件
1. `requirements.txt` - 添加 pandas, numpy, matplotlib
2. `app/workflows/state.py` - 添加 Python 相关状态字段
3. `app/workflows/graph.py` - 集成 Python 分析节点

### 功能变更
- ✅ 新增 Python 代码生成能力
- ✅ 新增 Python 代码执行能力（Local + AI-Sim）
- ✅ 新增 HTML/Markdown 报告生成
- ✅ 新增图表生成支持
- ✅ 工作流扩展到 12 个节点

---

## Phase 4: 人工反馈与多模型 (2024-04-26)

### 新增文件
1. `app/models/model_config.py` - ModelConfig ORM 模型
2. `app/models/human_feedback.py` - HumanFeedback ORM 模型
3. `app/schemas/model_config.py` - ModelConfig Schema
4. `app/schemas/human_feedback.py` - HumanFeedback Schema
5. `app/core/model_registry.py` - 模型注册表服务
6. `app/core/workflow_controller.py` - 工作流控制器
7. `app/api/model_config_controller.py` - 模型配置 API
8. `app/api/feedback_controller.py` - 人工反馈 API
9. `docs/PHASE4_DESIGN.md` - Phase 4 技术设计
10. `PHASE4_COMPLETE.md` - Phase 4 完成报告

### 修改文件
1. `app/models/__init__.py` - 导出新模型
2. `app/main.py` - 注册新路由

### 数据库变更
- ✅ 创建 `model_config` 表
- ✅ 创建 `human_feedback` 表

### 功能变更
- ✅ 新增多模型配置管理（8个 API）
- ✅ 新增人工反馈机制（4个 API）
- ✅ 新增工作流控制（暂停/恢复/取消）
- ✅ 新增模型注册表服务
- ✅ 支持模型热切换
- ✅ 支持模型测试

---

## Phase 2: 增强检索与计划 (2024-04-26)

### 新增文件
1. `app/core/vector_store.py` - 向量存储服务
2. `app/models/knowledge.py` - Knowledge ORM 模型
3. `app/schemas/knowledge.py` - Knowledge Schema
4. `app/services/knowledge_service.py` - 知识库服务
5. `app/api/agent_knowledge_controller.py` - 知识库 API
6. `app/models/semantic_model.py` - SemanticModel ORM 模型
7. `app/schemas/semantic_model.py` - SemanticModel Schema
8. `app/services/semantic_model_service.py` - 语义模型服务
9. `app/api/semantic_model_controller.py` - 语义模型 API
10. `app/models/query_plan.py` - QueryPlan ORM 模型
11. `app/schemas/query_plan.py` - QueryPlan Schema
12. `app/api/query_plan_controller.py` - 查询计划 API
13. `app/workflows/nodes/knowledge_recall.py` - 知识召回节点
14. `app/workflows/nodes/query_rewrite.py` - 查询改写节点
15. `app/workflows/nodes/planner.py` - 计划生成节点
16. `app/workflows/nodes/plan_executor.py` - 计划执行节点
17. `app/core/streaming_llm.py` - 流式 LLM 服务
18. `app/api/streaming_graph_controller.py` - 流式查询 API
19. `docs/PHASE2_DESIGN.md` - Phase 2 技术设计
20. `PHASE2_IMPLEMENTATION.md` - Phase 2 实现报告
21. `PHASE2_COMPLETE.md` - Phase 2 完成报告
22. `STREAMING_IMPLEMENTATION.md` - 流式输出文档

### 修改文件
1. `requirements.txt` - 添加 chromadb, sentence-transformers
2. `app/models/__init__.py` - 导出新模型
3. `app/main.py` - 注册新路由
4. `app/workflows/state.py` - 添加知识召回、计划相关状态字段
5. `app/workflows/graph.py` - 集成 RAG 节点
6. `app/workflows/nodes/sql_generate.py` - 使用改写查询和知识

### 数据库变更
- ✅ 创建 `knowledge` 表
- ✅ 创建 `semantic_model` 表
- ✅ 创建 `query_plan` 表

### 功能变更
- ✅ 新增向量数据库集成（Chroma）
- ✅ 新增知识库管理（6个 API）
- ✅ 新增 RAG 增强（知识召回 + 查询改写）
- ✅ 新增语义模型管理（6个 API）
- ✅ 新增查询计划生成与执行（4个 API）
- ✅ 新增流式输出（SSE）
- ✅ 工作流扩展到 8 个节点

---

## Phase 1: 核心 Text-to-SQL (2024-04-26)

### 新增文件
1. `app/core/config.py` - 配置管理
2. `app/core/database.py` - 数据库连接
3. `app/core/llm.py` - LLM 服务
4. `app/core/datasource_handler.py` - 数据库类型处理器
5. `app/models/agent.py` - Agent ORM 模型
6. `app/models/datasource.py` - Datasource ORM 模型
7. `app/models/agent_datasource.py` - AgentDatasource ORM 模型
8. `app/schemas/agent.py` - Agent Schema
9. `app/schemas/datasource.py` - Datasource Schema
10. `app/schemas/agent_datasource.py` - AgentDatasource Schema
11. `app/schemas/query.py` - Query Schema
12. `app/services/agent_service.py` - Agent 服务
13. `app/services/datasource_service.py` - Datasource 服务
14. `app/services/agent_datasource_service.py` - AgentDatasource 服务
15. `app/services/schema_service.py` - Schema 服务
16. `app/api/agent_controller.py` - Agent API
17. `app/api/datasource_controller.py` - Datasource API
18. `app/api/agent_datasource_controller.py` - AgentDatasource API
19. `app/api/schema_controller.py` - Schema API
20. `app/api/graph_controller.py` - 查询执行 API
21. `app/workflows/state.py` - 工作流状态定义
22. `app/workflows/graph.py` - 工作流图定义
23. `app/workflows/nodes/intent_recognition.py` - 意图识别节点
24. `app/workflows/nodes/schema_recall.py` - Schema 召回节点
25. `app/workflows/nodes/sql_generate.py` - SQL 生成节点
26. `app/workflows/nodes/sql_execute.py` - SQL 执行节点
27. `app/workflows/nodes/simple_report.py` - 简单报告节点
28. `app/main.py` - 应用入口
29. `.env` - 环境变量配置
30. `requirements.txt` - 依赖列表
31. `README.md` - 项目说明
32. `docs/PHASE1_DESIGN.md` - Phase 1 技术设计
33. `docs/DATABASE_DESIGN.md` - 数据库设计
34. `docs/API_DESIGN.md` - API 设计
35. `PHASE1_COMPLETE.md` - Phase 1 完成报告
36. `API_IMPLEMENTATION_STATUS.md` - API 实现统计
37. `SCHEMA_IMPROVEMENT.md` - Schema 改进文档

### 数据库变更
- ✅ 创建 `agent` 表
- ✅ 创建 `datasource` 表
- ✅ 创建 `agent_datasource` 表

### 功能变更
- ✅ 新增 Agent 管理（7个 API）
- ✅ 新增 Datasource 管理（6个 API）
- ✅ 新增 Agent-Datasource 关联（5个 API）
- ✅ 新增 Schema 查询（5个 API）
- ✅ 新增查询执行（1个 API）
- ✅ 新增基础工作流（5个节点）
- ✅ 支持 MySQL/PostgreSQL/SQLite

---

## API 命名对齐 (2024-04-26)

### 文件重命名
1. `app/api/agents.py` → `app/api/agent_controller.py`
2. `app/api/datasources.py` → `app/api/datasource_controller.py`
3. `app/api/agent_datasources.py` → `app/api/agent_datasource_controller.py`
4. `app/api/knowledge.py` → `app/api/agent_knowledge_controller.py`
5. `app/api/schema.py` → `app/api/schema_controller.py`
6. `app/api/query.py` → `app/api/graph_controller.py`
7. `app/api/streaming_query.py` → `app/api/streaming_graph_controller.py`

### 修改文件
1. `app/main.py` - 更新导入和路由注册

### 文档新增
1. `API_NAMING_ALIGNMENT.md` - API 命名对齐文档
2. `JAVA_PYTHON_MAPPING.md` - Java-Python 对应关系

---

## 项目文档 (2024-04-26)

### 新增文档
1. `PROJECT_PROGRESS.md` - 项目进度报告
2. `PROJECT_SUMMARY.md` - 项目总结
3. `QUICKSTART.md` - 快速开始指南
4. `MANUAL_START.md` - 手动启动指南

---

## 统计总结

### 文件统计
- **新增文件**: 60+ 个
- **修改文件**: 10+ 个
- **重命名文件**: 7 个
- **文档文件**: 20+ 个

### 代码统计
- **Models**: 6 个
- **Schemas**: 7 个
- **Services**: 6 个
- **API Controllers**: 9 个
- **Workflow Nodes**: 12 个
- **Core Services**: 6 个

### 数据库统计
- **表数量**: 6 张
- **总字段数**: 60+ 个

### API 统计
- **总接口数**: 41 个
- **Agent 管理**: 7 个
- **Datasource 管理**: 6 个
- **Agent-Datasource**: 5 个
- **Schema 查询**: 5 个
- **Knowledge 管理**: 6 个
- **SemanticModel 管理**: 6 个
- **QueryPlan 管理**: 4 个
- **查询执行**: 2 个

---

## 版本历史

### v0.4.0 (2024-04-26) - Phase 4 完成
- ✅ 多模型配置管理
- ✅ 人工反馈机制
- ✅ 工作流控制
- ✅ 模型热切换

### v0.3.0 (2024-04-26) - Phase 3 完成
- ✅ Python 代码生成与执行
- ✅ 数据分析能力
- ✅ 可视化报告生成
- ✅ 图表生成支持

### v0.2.0 (2024-04-26) - Phase 2 完成
- ✅ 向量数据库集成
- ✅ RAG 知识增强
- ✅ 语义模型管理
- ✅ 查询计划生成
- ✅ 流式输出

### v0.1.0 (2024-04-26) - Phase 1 完成
- ✅ 基础 Text-to-SQL
- ✅ Agent 管理
- ✅ Datasource 管理
- ✅ Schema 查询
- ✅ 基础工作流

---

## 下一版本计划

### v0.5.0 - Phase 5 (计划中)
- ⏳ Prompt 配置管理
- ⏳ 聊天会话管理
- ⏳ MCP 服务器
- ⏳ Langfuse 集成

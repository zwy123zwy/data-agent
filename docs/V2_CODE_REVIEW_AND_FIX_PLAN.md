# Python V2 代码问题对比与修复计划（对标 Java 版本）

## 目标

基于 `python-agent-v2` 当前代码，与 `DataAgent/data-agent-management` 的工程实现对比，识别高风险代码问题，并在本轮优先修复会影响稳定性和一致性的项。

## 对比基线

- Python: `python-agent-v2/app`
- Java: `DataAgent/data-agent-management/src/main/java`
- 参考点：
  - Java 动态模型注册：`service/aimodelconfig/AiModelRegistry.java`
  - Java 异常治理：`controller/GlobalExceptionHandler.java`
  - Java Agent 安全返回：`controller/AgentController.java` + `entity/Agent.java`

## 发现的问题

### P0

1. **模型字段保留字冲突风险（metadata）**
   - Python ORM 中使用 `metadata` 作为属性名会触发 SQLAlchemy Declarative 保留字异常。
   - 该问题会在 import 阶段直接导致服务启动失败。
   - 当前状态：已在前序修复中完成替换（`metadata_ = Column("metadata", ...)`）。

### P1

2. **LLM 模型硬编码为 `gpt-4`，与配置中心脱钩**
   - 多个节点直接写死 `model="gpt-4"`，与 Java 的 `AiModelRegistry` 动态模型机制不一致。
   - 风险：无法通过配置统一切换模型；不同环境行为漂移。
   - 涉及：`planner.py`、`query_rewrite.py`、`python_generate.py`、`python_analyze.py`、`code_executor.py`。

3. **Agent 响应暴露 `api_key` 字段**
   - Python `AgentResponse` 直接返回 `api_key`；Java 使用 `@JsonIgnore` 并提供专用 API key 管理接口。
   - 风险：敏感信息泄露。
   - 涉及：`app/schemas/agent.py`。

### P2

4. **列表总数统计使用全量加载再 `len()`**
   - 多处用 `select(entity)` + `len(count_result.all())` 统计总数。
   - 风险：数据量上来后内存和查询性能恶化。
   - 涉及：`knowledge_service.py`、`semantic_model_service.py`、`query_plan_controller.py`。

5. **向量检索结果对 metadata 判空不足**
   - `result["metadata"]["knowledge_id"]` 假设 metadata 恒存在。
   - 风险：当向量库返回缺失 metadata 的结果时触发 `KeyError/TypeError`。
   - 涉及：`knowledge_service.py`。

## 本轮修复范围

本轮按“先稳态、后增强”原则，计划修复：

1. LLM 模型硬编码问题（改为走统一配置 `settings.openai_model`）。
2. Agent 响应敏感字段暴露（移除 `api_key` 对外返回）。
3. 列表 count 查询改为数据库端 `COUNT(*)`。
4. 知识检索结果 metadata 判空与容错。

## 暂不处理（后续迭代）

- 完整对齐 Java 的全局异常治理结构（`@RestControllerAdvice` 对应 FastAPI 全局异常处理）
- 人审反馈链路端到端（创建-暂停-恢复）闭环增强
- 模型注册表缓存预热与热更新事件化机制

## 验收标准

- 应用可正常 import 与启动（不再出现 metadata 保留字错误）。
- 所有 LLM 调用模型由配置统一控制，不再硬编码 `gpt-4`。
- Agent 详情/列表接口响应不含明文 `api_key`。
- 列表接口总数统计不再全量拉取。
- 知识检索在 metadata 缺失时不抛异常。

## 本轮已完成修改

1. **LLM 模型统一走配置**
   - 将 `planner/query_rewrite/python_generate/python_analyze/code_executor` 中硬编码 `gpt-4` 改为 `settings.openai_model`。

2. **Agent 响应去除敏感字段**
   - `AgentResponse` 不再返回 `api_key`，仅保留 `api_key_enabled` 状态位。

3. **COUNT 查询优化**
   - `knowledge_service`、`semantic_model_service`、`query_plan_controller` 改为数据库侧 `COUNT(*)`，避免全量加载计数。

4. **向量检索容错**
   - `knowledge_service.search_knowledge` 增加 metadata 判空与 `knowledge_id` 缺失保护，异常结果自动跳过并记录 warning。

5. **全局异常治理（对齐 Java 的统一异常处理思路）**
   - 新增全局异常处理注册：`app/core/exception_handlers.py`
   - 在 `main.py` 注册 `HTTPException / RequestValidationError / Exception` 的统一错误响应结构。

6. **QueryPlan 响应结构收敛**
   - 新增 `ExecutePlanResponse`、`QueryPlanListResponse`
   - `execute_plan` 从混合 dict/模型返回统一为 `ExecutePlanResponse`
   - `list_plans` 从 `dict` 响应模型升级为强类型 `QueryPlanListResponse`

7. **业务成功响应统一化（阶段一）**
   - 新增 `SuccessResponse`（`success/message/data`）能力模型
   - 说明：为避免影响现有前端，本次已按兼容策略回退 `agent_controller` 与 `query_plan_controller` 的成功响应结构，保持原契约不变

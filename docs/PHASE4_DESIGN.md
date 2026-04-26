# Phase 4: 人工反馈与多模型 - 技术设计

## 目标

在 Phase 3 的基础上，增加人工反馈循环和多模型支持，提升系统的灵活性和可控性。

## 核心功能

### 1. 人工反馈机制
- 计划审批流程
- 反馈循环
- 中断与恢复
- 反馈历史记录

### 2. 多模型配置
- 模型配置管理
- 动态模型切换
- 模型注册表
- 模型性能监控

### 3. 流式输出优化
- LLM 流式输出集成
- 进度百分比
- 中断支持
- 错误恢复

---

## 人工反馈设计

### 工作流集成

```
用户查询
  ↓
意图识别
  ↓
知识召回
  ↓
查询改写
  ↓
Schema 召回
  ↓
计划生成
  ↓
【人工反馈点】→ 用户审批？
  ↓ 批准          ↓ 拒绝
SQL 执行      重新生成计划
  ↓
Python 分析
  ↓
报告生成
```

### HumanFeedbackNode 增强

```python
class HumanFeedbackNode:
    """人工反馈节点"""
    
    async def execute(self, state: WorkflowState) -> WorkflowState:
        # 1. 暂停工作流
        # 2. 等待用户反馈
        # 3. 根据反馈决定下一步
        pass
```

### 反馈类型

1. **计划审批**
   - 批准：继续执行
   - 拒绝：重新生成计划
   - 修改：用户修改计划后继续

2. **SQL 审批**
   - 批准：执行 SQL
   - 拒绝：重新生成 SQL
   - 修改：用户修改 SQL 后执行

3. **Python 代码审批**
   - 批准：执行代码
   - 拒绝：重新生成代码
   - 修改：用户修改代码后执行

---

## 多模型配置设计

### 数据库表

```sql
CREATE TABLE model_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL COMMENT '模型名称',
    type VARCHAR(50) NOT NULL COMMENT '模型类型: chat, embedding',
    provider VARCHAR(50) NOT NULL COMMENT '提供商: openai, anthropic, qwen',
    model_id VARCHAR(100) NOT NULL COMMENT '模型ID',
    api_key VARCHAR(255) COMMENT 'API Key',
    api_base VARCHAR(255) COMMENT 'API Base URL',
    temperature FLOAT DEFAULT 0.0 COMMENT '温度参数',
    max_tokens INT COMMENT '最大 Token 数',
    enabled BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    is_default BOOLEAN DEFAULT FALSE COMMENT '是否默认',
    metadata JSON COMMENT '其他配置',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (type),
    INDEX idx_enabled (enabled)
) COMMENT='模型配置';
```

### ModelRegistry 服务

```python
class ModelRegistry:
    """模型注册表"""
    
    def __init__(self):
        self.models: Dict[str, ModelConfig] = {}
        self.default_chat_model: Optional[str] = None
        self.default_embedding_model: Optional[str] = None
    
    def register_model(self, config: ModelConfig):
        """注册模型"""
        pass
    
    def get_model(self, name: str) -> ModelConfig:
        """获取模型配置"""
        pass
    
    def get_default_chat_model(self) -> ModelConfig:
        """获取默认聊天模型"""
        pass
    
    def switch_model(self, name: str):
        """切换模型"""
        pass
```

### 模型配置 API

```python
# 创建模型配置
POST /api/models
{
    "name": "gpt-4",
    "type": "chat",
    "provider": "openai",
    "model_id": "gpt-4",
    "api_key": "sk-...",
    "temperature": 0.0
}

# 列出模型配置
GET /api/models?type=chat

# 获取模型详情
GET /api/models/{id}

# 更新模型配置
PUT /api/models/{id}

# 删除模型配置
DELETE /api/models/{id}

# 设置默认模型
POST /api/models/{id}/set-default

# 切换模型
POST /api/models/{id}/switch
```

---

## 流式输出优化

### LLM 流式集成

```python
async def sql_generate_node_streaming(state: WorkflowState):
    """SQL 生成节点（流式）"""
    
    llm = get_streaming_llm()
    
    # 流式生成 SQL
    sql_chunks = []
    async for chunk in llm.chat_stream(system_prompt, user_prompt):
        sql_chunks.append(chunk)
        # 发送 SSE 事件
        yield {
            "event": "sql_chunk",
            "data": {"chunk": chunk}
        }
    
    sql = "".join(sql_chunks)
    return {"generated_sql": sql}
```

### 进度跟踪

```python
class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(self, total_steps: int):
        self.total_steps = total_steps
        self.current_step = 0
    
    def update(self, step_name: str):
        """更新进度"""
        self.current_step += 1
        percent = (self.current_step / self.total_steps) * 100
        
        return {
            "event": "progress",
            "data": {
                "step": step_name,
                "current": self.current_step,
                "total": self.total_steps,
                "percent": percent
            }
        }
```

### 中断支持

```python
class WorkflowController:
    """工作流控制器"""
    
    def __init__(self):
        self.running_workflows: Dict[str, WorkflowState] = {}
    
    async def start_workflow(self, workflow_id: str, state: WorkflowState):
        """启动工作流"""
        self.running_workflows[workflow_id] = state
        # 执行工作流
        pass
    
    async def pause_workflow(self, workflow_id: str):
        """暂停工作流"""
        pass
    
    async def resume_workflow(self, workflow_id: str, feedback: Any):
        """恢复工作流"""
        pass
    
    async def cancel_workflow(self, workflow_id: str):
        """取消工作流"""
        pass
```

---

## 实现步骤

### Step 1: 人工反馈基础 (1天)
- [ ] 创建 HumanFeedback 模型和 Schema
- [ ] 实现 HumanFeedbackNode
- [ ] 实现反馈 API
- [ ] 工作流中断与恢复

### Step 2: 反馈流程集成 (1天)
- [ ] 计划审批流程
- [ ] SQL 审批流程
- [ ] Python 代码审批流程
- [ ] 反馈历史记录

### Step 3: 模型配置管理 (1天)
- [ ] 创建 ModelConfig 模型和 Schema
- [ ] 实现 ModelRegistry 服务
- [ ] 实现模型配置 API
- [ ] 模型切换功能

### Step 4: 流式输出优化 (1天)
- [ ] LLM 流式输出集成
- [ ] 进度跟踪器
- [ ] 中断支持
- [ ] 错误恢复

### Step 5: 测试与优化 (1天)
- [ ] 端到端测试
- [ ] 性能优化
- [ ] 文档完善

---

## API 设计

### 人工反馈 API

```python
# 获取待审批的任务
GET /api/feedback/pending

# 提交反馈
POST /api/feedback/{workflow_id}
{
    "action": "approve",  # approve, reject, modify
    "comment": "看起来不错",
    "modified_content": null  # 如果是 modify，提供修改后的内容
}

# 获取反馈历史
GET /api/feedback/history?workflow_id={id}
```

### 模型配置 API

```python
# 创建模型配置
POST /api/models

# 列出模型配置
GET /api/models

# 获取模型详情
GET /api/models/{id}

# 更新模型配置
PUT /api/models/{id}

# 删除模型配置
DELETE /api/models/{id}

# 设置默认模型
POST /api/models/{id}/set-default

# 测试模型
POST /api/models/{id}/test
```

### 工作流控制 API

```python
# 暂停工作流
POST /api/workflows/{id}/pause

# 恢复工作流
POST /api/workflows/{id}/resume

# 取消工作流
POST /api/workflows/{id}/cancel

# 获取工作流状态
GET /api/workflows/{id}/status
```

---

## 测试用例

### 人工反馈测试

```python
# 1. 启动需要审批的查询
response = client.post("/api/query", json={
    "agent_id": 1,
    "query": "删除所有用户数据",
    "require_approval": True
})

workflow_id = response.json()["workflow_id"]

# 2. 获取待审批任务
pending = client.get("/api/feedback/pending")
assert len(pending.json()) == 1

# 3. 拒绝执行
client.post(f"/api/feedback/{workflow_id}", json={
    "action": "reject",
    "comment": "这个操作太危险了"
})

# 4. 验证工作流已取消
status = client.get(f"/api/workflows/{workflow_id}/status")
assert status.json()["status"] == "cancelled"
```

### 模型切换测试

```python
# 1. 创建模型配置
client.post("/api/models", json={
    "name": "gpt-4",
    "type": "chat",
    "provider": "openai",
    "model_id": "gpt-4"
})

# 2. 设置为默认
client.post("/api/models/1/set-default")

# 3. 执行查询（使用新模型）
response = client.post("/api/query", json={
    "agent_id": 1,
    "query": "查询用户数量"
})

# 4. 验证使用了正确的模型
assert response.json()["model_used"] == "gpt-4"
```

---

## 成功标准

- ✅ 人工反馈流程完整
- ✅ 支持计划/SQL/代码审批
- ✅ 模型配置管理完整
- ✅ 支持至少 3 种模型
- ✅ 模型热切换无缝
- ✅ 流式输出优化
- ✅ 进度跟踪准确
- ✅ 中断恢复正常

---

## 风险与挑战

1. **工作流状态管理** - 需要持久化中断的工作流状态
2. **并发控制** - 多个工作流同时运行时的资源管理
3. **模型兼容性** - 不同模型的 API 差异
4. **性能影响** - 人工反馈可能导致长时间等待

---

## 下一步

完成 Phase 4 后，进入 Phase 5：完整 API 与管理。

# Phase 3: Python 分析与报告 - 技术设计

## 目标

在 Phase 2 的基础上，增加 Python 数据分析和可视化报告生成能力。

## 核心功能

### 1. Python 代码生成
- 基于 SQL 查询结果生成 Python 分析代码
- 支持数据清洗、统计分析、趋势分析
- 自动选择合适的分析方法

### 2. Python 代码执行
- 本地执行模式（Local）
- Docker 容器执行（隔离环境）
- AI 模拟执行（无实际执行）

### 3. 图表生成
- matplotlib 基础图表
- 支持折线图、柱状图、饼图、散点图
- 图表自动保存和嵌入

### 4. 报告生成
- HTML 格式报告
- Markdown 格式报告
- 包含图表、表格、分析结论

---

## 技术选型

### Python 执行环境
**选择**: **Local + Docker**

**模式**:
1. **Local** - 直接在本地执行（开发环境）
2. **Docker** - 容器隔离执行（生产环境）
3. **AI-Sim** - LLM 模拟执行结果（无实际执行）

### 图表库
**选择**: **matplotlib**

**理由**:
- Python 标准图表库
- 功能完整
- 易于集成

**备选**:
- plotly (交互式图表)
- seaborn (统计图表)

### 报告格式
**选择**: **HTML + Markdown**

---

## 工作流节点

### 新增节点

#### 1. PythonGenerateNode
- 输入：SQL 查询结果
- 输出：Python 分析代码
- 功能：根据数据特征生成分析代码

#### 2. PythonExecuteNode
- 输入：Python 代码 + 数据
- 输出：执行结果（数据 + 图表）
- 功能：执行代码并捕获输出

#### 3. PythonAnalyzeNode
- 输入：执行结果
- 输出：分析结论
- 功能：解读执行结果，生成文字描述

#### 4. ReportGeneratorNode
- 输入：所有节点的输出
- 输出：HTML/Markdown 报告
- 功能：汇总生成完整报告

---

## 工作流更新

### 完整工作流 (12个节点)

```
用户查询
  ↓
意图识别 → 闲聊？→ 直接回复
  ↓ 数据分析
知识召回（RAG）
  ↓
查询改写
  ↓
Schema 召回
  ↓
计划生成 → 简单查询？→ SQL生成 → SQL执行 → Python生成 → Python执行 → Python分析 → 报告生成
  ↓ 复杂查询
计划执行（多步骤）
  ↓
报告生成
```

---

## 代码执行器设计

### CodeExecutor 接口

```python
class CodeExecutor(ABC):
    @abstractmethod
    async def execute(self, code: str, data: Any) -> ExecutionResult:
        """执行代码"""
        pass
```

### 实现类

#### 1. LocalExecutor
```python
class LocalExecutor(CodeExecutor):
    async def execute(self, code: str, data: Any) -> ExecutionResult:
        # 使用 subprocess 执行
        # 捕获 stdout, stderr
        # 保存生成的图表
        pass
```

#### 2. DockerExecutor
```python
class DockerExecutor(CodeExecutor):
    async def execute(self, code: str, data: Any) -> ExecutionResult:
        # 创建临时容器
        # 挂载数据和代码
        # 执行并收集结果
        # 清理容器
        pass
```

#### 3. AISimExecutor
```python
class AISimExecutor(CodeExecutor):
    async def execute(self, code: str, data: Any) -> ExecutionResult:
        # 使用 LLM 模拟执行结果
        # 不实际运行代码
        pass
```

---

## 依赖更新

```txt
# 数据分析
pandas==2.1.4
numpy==1.26.2

# 图表生成
matplotlib==3.8.2

# Docker 支持（可选）
docker==7.0.0
```

---

## 安全考虑

### 代码执行安全

1. **沙箱隔离**
   - Docker 容器隔离
   - 资源限制（CPU、内存、时间）
   - 网络隔离

2. **代码审查**
   - 禁止危险操作（文件系统、网络）
   - 白名单机制
   - 代码静态分析

3. **超时控制**
   - 执行时间限制（默认 30 秒）
   - 自动终止超时任务

---

## 报告模板

### HTML 报告结构

```html
<!DOCTYPE html>
<html>
<head>
    <title>数据分析报告</title>
    <style>
        /* 样式 */
    </style>
</head>
<body>
    <h1>数据分析报告</h1>
    
    <section class="query">
        <h2>查询</h2>
        <p>用户查询: ...</p>
        <pre>SQL: ...</pre>
    </section>
    
    <section class="data">
        <h2>数据</h2>
        <table>...</table>
    </section>
    
    <section class="analysis">
        <h2>分析</h2>
        <img src="chart.png" />
        <p>分析结论: ...</p>
    </section>
    
    <section class="summary">
        <h2>总结</h2>
        <p>...</p>
    </section>
</body>
</html>
```

---

## 实现步骤

### Step 1: 代码执行器 (1天)
- [ ] 创建 CodeExecutor 接口
- [ ] 实现 LocalExecutor
- [ ] 实现 AISimExecutor
- [ ] 测试代码执行

### Step 2: Python 节点 (1天)
- [ ] 实现 PythonGenerateNode
- [ ] 实现 PythonExecuteNode
- [ ] 实现 PythonAnalyzeNode
- [ ] 集成到工作流

### Step 3: 图表生成 (1天)
- [ ] 集成 matplotlib
- [ ] 实现图表生成逻辑
- [ ] 图表保存和管理

### Step 4: 报告生成 (1天)
- [ ] 实现 ReportGeneratorNode
- [ ] HTML 报告模板
- [ ] Markdown 报告模板
- [ ] 图表嵌入

### Step 5: Docker 执行器 (可选，1天)
- [ ] 实现 DockerExecutor
- [ ] Docker 镜像构建
- [ ] 容器管理

---

## 测试用例

### Python 代码生成测试

```python
# 输入：SQL 结果
sql_result = [
    {"month": "2024-01", "sales": 10000},
    {"month": "2024-02", "sales": 12000},
    {"month": "2024-03", "sales": 15000}
]

# 期望生成的代码
expected_code = """
import pandas as pd
import matplotlib.pyplot as plt

# 数据加载
data = pd.DataFrame(sql_result)

# 绘制折线图
plt.figure(figsize=(10, 6))
plt.plot(data['month'], data['sales'])
plt.title('月度销售趋势')
plt.xlabel('月份')
plt.ylabel('销售额')
plt.savefig('sales_trend.png')
plt.close()

# 统计分析
print(f"平均销售额: {data['sales'].mean()}")
print(f"总销售额: {data['sales'].sum()}")
"""
```

### 报告生成测试

```python
# 输入：完整的工作流状态
state = {
    "user_query": "分析最近3个月的销售趋势",
    "generated_sql": "SELECT ...",
    "sql_result": [...],
    "python_code": "...",
    "python_result": {...},
    "charts": ["sales_trend.png"]
}

# 期望输出：HTML 报告
expected_report = """
<html>
...
</html>
"""
```

---

## 成功标准

- ✅ Python 代码能正确生成
- ✅ 代码能安全执行
- ✅ 图表能正确生成
- ✅ 报告格式完整美观
- ✅ 执行时间 < 30 秒
- ✅ 支持至少 3 种图表类型

---

## 风险与挑战

1. **代码执行安全** - 需要严格的沙箱隔离
2. **执行超时** - 需要合理的超时控制
3. **图表质量** - 需要调优图表参数
4. **报告美观度** - 需要精心设计模板

---

## 下一步

完成 Phase 3 后，进入 Phase 4：人工反馈与多模型。

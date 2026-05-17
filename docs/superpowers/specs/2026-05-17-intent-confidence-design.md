# 意图识别置信度 + 人工确认闭环

## 问题

1. 意图识别无准确度衡量 — LLM 输出直接用，不知道它对不对
2. 无人工纠正机制 — 误判后用户无法干预
3. `multi_turn_context` 恒为空 — `MultiTurnContextManager` 已实现但未接入 Controller

## 设计

### 置信度三层阈值

```
confidence >= 0.7 → 直接接受
confidence < 0.7  → interrupt() 暂停，等人工确认
                    人工反馈 → LLM 重判一次
                    重判后仍 < 0.7 → 以人工答案为准
                    最多重判 1 次
```

### 人工确认流程

复用现有 `interrupt()` + `Command(resume=...)` 机制：

```
用户发 query
  → intent_recognition 执行
  → LLM 返回 confidence=0.6 (< 0.7)
  → interrupt({"type": "intent_confirm", "guessed_intent": "data_analysis", "confidence": 0.6})
  → Controller 捕获 __interrupt__，发送 paused 事件
  → 前端展示: "我判断你的意图可能是「数据分析」(置信度 60%)，请确认或纠正"
  → 用户回复 "是的，帮我查销售数据" 或 "不对，我只是闲聊"
  → 前端再次调用 /api/stream/search?threadId=xxx&humanFeedbackContent=...
  → Controller 用 Command(resume={"action": "approve", "reason": "..."}) 恢复
  → intent_recognition 重新执行，interrupt() 返回用户反馈
  → 拼接重判 prompt: "用户问题: xxx / 你上次判断为X / 用户反馈: xxx / 请重新判断"
  → LLM 重判 → confidence >= 0.7 → 通过
```

### 多轮对话接入

```
请求进入 → get_multi_turn_manager().get_context_for_prompt(threadId)
         → 写入 state.multi_turn_context
         → intent_recognition 读 multi_turn_context 拼入 prompt

请求完成 → get_multi_turn_manager().add_turn(threadId, query, response_summary)
```

## 涉及文件

| 文件 | 改动 |
|------|------|
| `app/workflows/state.py` | 加 `INTENT_CONFIDENCE`, `INTENT_NEEDS_CONFIRM`, `INTENT_RETRY_COUNT`, `INTENT_HUMAN_FEEDBACK` |
| `app/workflows/nodes/intent_recognition.py` | prompt 加 confidence, `_call_llm()` 提取方法, `_build_prompt()` 支持重判/多轮模式, `interrupt()` 暂停 |
| `app/workflows/graph.py` | 无路由改动 (interrupt 在节点内部处理) |
| `app/api/streaming_graph_controller.py` | 接入 `MultiTurnContextManager`, interrupt 类型检测 (intent_confirm vs human_feedback), `add_turn` 记录 |

## 关键阈值

| 常量 | 值 | 位置 |
|------|-----|------|
| `CONFIDENCE_THRESHOLD` | 0.7 | `intent_recognition.py` |
| `MAX_RETRY` | 1 | `intent_recognition.py` |

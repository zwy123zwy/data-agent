# [阶段1] Harness V2 业务包 — 全新实现，不复用 workflows / wrap_v1

"""V2 主路径实现：感知、规划、编排、工具（见 openspec/changes/harness-v2-greenfield）。"""

# TODO(H2): app/harness/memory/ 目录已清空（多轮记忆暂缓），仅残留空 __pycache__。
#   H2 实施时需重新创建 memory 模块（ThreadMemoryService + 摘要压缩）。
#   当前 memory 字段在 builder.py 中恒为 []，Gateway 不读历史，Agent 不感知上下文。
# 答：与 tasks.md「2.1 暂缓」一致。重开 H2 时新建 memory/ 门面：chat_message 为 SSOT、
#   Run 结束 Commit assistant 摘要；设计见后续独立设计稿或 PHASE-1-2-IMPLEMENTATION-MAP §8。

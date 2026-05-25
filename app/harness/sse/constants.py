# [阶段1] SSE 载荷通用常量

SUMMARY_MAX_LEN = 200


def truncate_summary(text: str, max_len: int = SUMMARY_MAX_LEN) -> str:
    """[阶段1] 人类可读摘要上限，与前端展示一致。"""
    return (text or "")[:max_len]

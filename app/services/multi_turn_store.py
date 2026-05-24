# [阶段4] 多轮工作记忆存储：DB 消息配对与 sync 策略（Harness Memory #4）

from __future__ import annotations

from typing import Any, List, Sequence, Tuple

_HYDRATE_USER_MAX = 500
_HYDRATE_ASSISTANT_MAX = 500


def pair_messages_to_turns(
    messages: Sequence[Any],
    *,
    user_max: int = _HYDRATE_USER_MAX,
    assistant_max: int = _HYDRATE_ASSISTANT_MAX,
) -> List[Tuple[str, str]]:
    """[阶段4] 将 chat_message 序列表配对为 (user_query, assistant_response) 列表。"""
    pending_user: str | None = None
    paired: list[tuple[str, str]] = []

    for msg in messages:
        role = getattr(msg, "role", None) or (
            msg.get("role") if isinstance(msg, dict) else None
        )
        content = getattr(msg, "content", None) or (
            msg.get("content") if isinstance(msg, dict) else ""
        )
        text = (content or "").strip()
        if not text:
            continue
        if role == "user":
            if pending_user:
                # [阶段2] 连续 user 消息：保留上一轮（空 assistant），避免静默丢弃
                paired.append((pending_user, ""))
            pending_user = text[:user_max]
        elif role == "assistant":
            if pending_user:
                paired.append((pending_user, text[:assistant_max]))
                pending_user = None
            elif text:
                paired.append(("", text[:assistant_max]))

    if pending_user:
        paired.append((pending_user, ""))

    return paired


def merge_db_and_memory_turns(
    db_pairs: List[Tuple[str, str]],
    memory_pairs: List[Tuple[str, str]],
    *,
    sync_mode: str,
    max_turns: int,
) -> List[Tuple[str, str]]:
    """[阶段4] 按 sync_mode 合并 DB 与内存轮次，并裁剪到 max_turns。

    replace: 仅保留 DB 配对结果。
    merge: DB 为基底；内存轮数多于 DB 时追加内存尾部（Run 内 add_turn 未落库）。
    """
    mode = (sync_mode or "merge").lower()
    if mode == "replace":
        merged = list(db_pairs)
    else:
        merged = list(db_pairs)
        if len(memory_pairs) > len(db_pairs):
            merged.extend(memory_pairs[len(db_pairs) :])

    if max_turns > 0 and len(merged) > max_turns:
        merged = merged[-max_turns:]
    return merged

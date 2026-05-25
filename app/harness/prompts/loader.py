# [阶段1] 系统提示词加载：文件 SSOT + DB 追加 + Run override

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.config import settings
from app.harness.prompts.keys import HarnessPromptKey, db_prompt_type

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# 定义后端根目录路径
_BACKEND_ROOT = Path(__file__).resolve().parents[3]
# Agent自定义追加部分的标题头
_AGENT_APPEND_HEADER = "## Agent 自定义"


def _prompts_dir() -> Path:
    """
    获取提示词文件目录的路径
    
    Returns:
        Path: 提示词文件目录的绝对路径
    """
    rel = (settings.harness_prompts_dir or "prompts/harness").strip()
    path = Path(rel)
    if not path.is_absolute():
        path = _BACKEND_ROOT / path
    return path


def _file_path(key: HarnessPromptKey) -> Path:
    """
    根据提示词键获取对应的文件路径
    
    Args:
        key: 提示词的键值
        
    Returns:
        Path: 对应的提示词文件路径
    """
    return _prompts_dir() / f"{key.value}.system.md"


def _read_file(path: Path) -> str:
    """
    读取指定路径的文件内容
    
    Args:
        path: 文件路径
        
    Returns:
        str: 文件内容的字符串
        
    Raises:
        FileNotFoundError: 当文件不存在时抛出异常
        ValueError: 当文件为空时抛出异常
    """
    if not path.is_file():
        raise FileNotFoundError(f"Prompt 文件不存在: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Prompt 文件为空: {path}")
    return text


@lru_cache(maxsize=32)
def _cached_file_text(path_str: str, mtime_ns: int) -> str:
    """[阶段1] 按 mtime 缓存文件内容；mtime 变化时自动失效。"""
    return _read_file(Path(path_str))


def load_prompt_file(key: HarnessPromptKey) -> str:
    """
    从L0仓库文件加载系统提示词
    
    Args:
        key: 提示词的键值
        
    Returns:
        str: 加载的提示词内容
    """
    path = _file_path(key)
    if getattr(settings, "harness_prompts_hot_reload", False):
        return _read_file(path)
    mtime_ns = path.stat().st_mtime_ns if path.is_file() else 0
    return _cached_file_text(str(path), mtime_ns)


def _apply_run_override(
    base: str,
    key: HarnessPromptKey,
    overrides: dict[str, str] | None,
) -> str:
    """
    应用运行时重写配置到基础提示词
    
    Args:
        base: 基础提示词内容
        key: 提示词的键值
        overrides: 重写配置字典
        
    Returns:
        str: 应用重写后的提示词内容
    """
    if not overrides:
        return base
    raw = overrides.get(key.value) or overrides.get(str(key))
    if raw and raw.strip():
        return raw.strip()
    return base


async def _db_append(
    base: str,
    key: HarnessPromptKey,
    db: AsyncSession,
    agent_id: int | None,
) -> str:
    """
    从数据库中获取附加的提示词内容并追加到基础内容上
    
    Args:
        base: 基础提示词内容
        key: 提示词的键值
        db: 数据库异步会话
        agent_id: Agent的ID，可选
        
    Returns:
        str: 包含数据库附加内容的提示词
    """
    from app.services.prompt_config_service import PromptConfigService

    prompt_type = db_prompt_type(key)
    configs: list = []
    # 根据agent_id获取特定Agent的配置
    if agent_id is not None:
        configs.extend(
            await PromptConfigService.get_active_all_by_type(
                db, prompt_type, agent_id=agent_id
            )
        )
    # 获取全局配置
    configs.extend(
        await PromptConfigService.get_active_all_by_type(db, prompt_type, agent_id=None)
    )
    seen: set[str] = set()
    chunks: list[str] = []
    # 过滤重复内容并构建配置块列表
    for cfg in configs:
        text = (cfg.system_prompt or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        chunks.append(text)
    if not chunks:
        return base
    return base + "\n\n" + _AGENT_APPEND_HEADER + "\n" + "\n\n".join(chunks)


def get_system_prompt_sync(
    key: HarnessPromptKey,
    *,
    overrides: dict[str, str] | None = None,
) -> str:
    """[阶段1] 同步解析：L0 文件 + L2 override（Tool 路径，无 DB）。"""
    base = load_prompt_file(key)
    return _apply_run_override(base, key, overrides)


async def get_system_prompt(
    key: HarnessPromptKey,
    *,
    db: AsyncSession | None = None,
    agent_id: int | None = None,
    overrides: dict[str, str] | None = None,
) -> str:
    """
    异步解析提示词：L0 文件 + L1 数据库 + L2 重写；当override非空时跳过L1数据库查询
    
    Args:
        key: 提示词的键值
        db: 数据库异步会话，可选
        agent_id: Agent的ID，可选
        overrides: 重写配置字典，可选
        
    Returns:
        str: 解析完成的提示词内容
    """
    base = load_prompt_file(key)
    if overrides and (overrides.get(key.value) or overrides.get(str(key))):
        return _apply_run_override(base, key, overrides)
    if db is not None:
        try:
            base = await _db_append(base, key, db, agent_id)
        except Exception as exc:
            logger.warning("[阶段1][PromptLoader] DB 追加失败 key=%s: %s", key, exc)
    return _apply_run_override(base, key, overrides)


def clear_prompt_cache() -> None:
    """[阶段1] 测试或热更新后清空文件缓存。"""
    _cached_file_text.cache_clear()
"""
统一 LLM 服务 — 所有 AI 调用的唯一出口

【模型配置优先级】
  1. ModelRegistry (MySQL model_config 表, is_active=1)  ← 热切换
  2. .env 文件 (OPENAI_API_KEY/BASE/MODEL)             ← 兜底

【热切换流程 — 对齐 Java AiModelRegistry + LlmService】
  1. 用户 POST /api/model-config/activate/{id}
  2. ModelConfigOpsService → DB 更新 → llm_service.invalidate()  ← 清缓存
  3. 下一个 LLM 调用 → _ensure_configured() 检测到 needs_rebuild
     → 查 DB 获取激活模型 → configure() 重建客户端
  4. 后续调用直接命中缓存，零 DB 开销

【Java 对应】
  清缓存:  refreshChat() → currentChatClient = null
  懒重建:  getChatClient() → if null → DB 查询 → 重建
  Python:  invalidate() → _needs_rebuild = True
           _ensure_configured() → if True → DB 查询 → configure()

【全局单例】
  llm_service = LLMService() — 模块级单例，所有节点共享
"""
from typing import Optional, AsyncIterator
from openai import AsyncOpenAI
from .config import settings
import logging
import time
import inspect

logger = logging.getLogger(__name__)

# 全局 LLM 调用计数器
_llm_call_counter = 0


class LLMService:
    """LLM 服务封装 — 所有 AI 调用的统一入口

    热切换机制（对齐 Java）:
      - invalidate() 标记缓存失效（activate 时调用）
      - _ensure_configured() 在首次 chat/chat_stream 时按需重建
      - 99%+ 的请求只是检查 _needs_rebuild flag，不查 DB
    """

    def __init__(self):
        self._load_from_env()
        self._source = "env"
        self._needs_rebuild = True  # 启动后首次调用需要加载 DB 配置
        self._session_factory = None

    def set_session_factory(self, factory):
        """注入异步 session 工厂（由 lifespan 启动时调用，避免循环导入）"""
        self._session_factory = factory

    def _load_from_env(self):
        """从 .env 加载默认配置"""
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
        )
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature

    def configure(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.0,
    ):
        """从 DB 热切换模型配置"""
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.temperature = temperature
        self._source = "db"
        logger.info(
            "[LLMService] Hot-switched to DB model: %s @ %s (temp=%.2f)",
            model, base_url, temperature,
        )

    def reset(self):
        """回退到 .env 默认配置"""
        self._load_from_env()
        self._source = "env"
        logger.info(
            "[LLMService] Reset to .env model: %s @ %s",
            self.model, settings.openai_api_base,
        )

    def invalidate(self):
        """标记缓存失效 — 对齐 Java AiModelRegistry.refreshChat()

        activate 模型后调用，不查 DB，只是设置标记。
        下一个 chat()/chat_stream() 调用时 _ensure_configured() 会按需重建。
        """
        self._needs_rebuild = True
        logger.info("[LLMService] Cache invalidated, will rebuild on next call")

    async def _ensure_configured(self):
        """按需从 DB 重建客户端 — 对齐 Java getChatClient() 的 lazy rebuild

        只在 _needs_rebuild=True 时才查 DB 并重建。
        如果 DB 中有激活的 CHAT 模型 → configure()
        如果 DB 中没有 → reset() 回退 .env
        """
        if not self._needs_rebuild:
            return

        self._needs_rebuild = False

        if self._session_factory is None:
            return

        try:
            from sqlalchemy import select
            from ..models.model_config import ModelConfig

            async with self._session_factory() as db:
                result = await db.execute(
                    select(ModelConfig).filter(
                        ModelConfig.model_type == "CHAT",
                        ModelConfig.is_active == 1,
                        ModelConfig.is_deleted == 0,
                    )
                )
                model_config = result.scalar_one_or_none()

                if model_config:
                    self.configure(
                        api_key=model_config.api_key,
                        base_url=model_config.base_url,
                        model=model_config.model_name,
                        temperature=float(model_config.temperature or 0.0),
                    )
                elif self._source != "env":
                    self.reset()
        except Exception as e:
            logger.error("[LLMService] Failed to load model from DB: %s, using env fallback", e)
            if self._source != "env":
                self.reset()

    @property
    def source(self) -> str:
        """当前配置来源: 'env' 或 'db'"""
        return self._source

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> str:
        """非流式调用 LLM"""
        await self._ensure_configured()

        global _llm_call_counter
        _llm_call_counter += 1
        call_id = _llm_call_counter

        caller = "unknown"
        for frame in inspect.stack():
            mod = frame.frame.f_globals.get("__name__", "")
            if "workflows.nodes" in mod or "services" in mod or "core" in mod:
                caller = mod
                break

        temp = temperature if temperature is not None else self.temperature
        input_preview = user_prompt[:200].replace("\n", "\\n")

        logger.info(
            "[LLM #%d] >>> CALL model=%s source=%s caller=%s temp=%.2f input_len=%d",
            call_id, self.model, self._source, caller, temp, len(user_prompt),
        )
        logger.debug("[LLM #%d] >>> INPUT: %s...", call_id, input_preview)

        t_start = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temp,
            )
        except Exception:
            elapsed = time.time() - t_start
            logger.error(
                "[LLM #%d] <<< ERROR model=%s caller=%s elapsed=%.2fs",
                call_id, self.model, caller, elapsed,
            )
            raise

        elapsed = time.time() - t_start
        content = response.choices[0].message.content

        usage = response.usage
        if usage:
            logger.info(
                "[LLM #%d] <<< DONE model=%s caller=%s elapsed=%.2fs "
                "output_len=%d input_tokens=%d output_tokens=%d total_tokens=%d",
                call_id, self.model, caller, elapsed,
                len(content) if content else 0,
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
            )
        else:
            logger.info(
                "[LLM #%d] <<< DONE model=%s caller=%s elapsed=%.2fs output_len=%d",
                call_id, self.model, caller, elapsed,
                len(content) if content else 0,
            )

        output_preview = (content or "")[:300].replace("\n", "\\n")
        logger.debug("[LLM #%d] <<< OUTPUT: %s...", call_id, output_preview)

        return content

    async def chat_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
    ) -> AsyncIterator[str]:
        """流式调用 LLM"""
        await self._ensure_configured()

        global _llm_call_counter
        _llm_call_counter += 1
        call_id = _llm_call_counter

        caller = "unknown"
        for frame in inspect.stack():
            mod = frame.frame.f_globals.get("__name__", "")
            if "workflows.nodes" in mod or "services" in mod or "core" in mod:
                caller = mod
                break

        temp = temperature if temperature is not None else self.temperature

        logger.info(
            "[LLM #%d] >>> STREAM model=%s source=%s caller=%s temp=%.2f input_len=%d",
            call_id, self.model, self._source, caller, temp, len(user_prompt),
        )

        t_start = time.time()
        total_content = []
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temp,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    total_content.append(chunk.choices[0].delta.content)
                    yield chunk.choices[0].delta.content

        finally:
            elapsed = time.time() - t_start
            total = "".join(total_content)
            logger.info(
                "[LLM #%d] <<< STREAM_DONE model=%s caller=%s elapsed=%.2fs output_len=%d",
                call_id, self.model, caller, elapsed, len(total),
            )


# 全局 LLM 服务实例
llm_service = LLMService()


def get_llm_client() -> AsyncOpenAI:
    """获取底层 OpenAI 客户端（复用连接池）"""
    return llm_service.client

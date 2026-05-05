"""
统一 LLM 服务 — 所有 AI 调用的唯一出口

【在系统中的地位】
  本服务是整个后端唯一的 LLM 调用入口。所有工作流节点、所有需要 AI
  能力的模块都通过这里的 chat() / chat_stream() 调用大模型。

【模块连接】
  调用者 (谁依赖 LLMService):
    - workflows/nodes/*.py (16 个节点) → 每个节点调用 llm_service.chat()
      例: intent_recognition → 判断意图
          sql_generate       → 生成 SQL
          python_generate    → 生成 Python 代码
          report_generator   → 生成最终报告
    - core/model_registry.py → 测试模型连接时调用
    - services/knowledge_service.py → (间接) 通过 vector_store 生成 embedding

  被依赖:
    - core/config.py → 读取 OPENAI_API_KEY, OPENAI_API_BASE, OPENAI_MODEL
    - openai.AsyncOpenAI → 底层 HTTP 客户端 (复用连接池)

  Java 对应:
    LLMService ≈ LlmService.java (Spring AI 的 ChatClient 封装)

【两种调用模式】
  chat()         → 非流式: 等待完整响应后返回 → 用于工作流节点 (需要完整结果)
  chat_stream()  → 流式:   逐 token 返回      → 用于 SSE 场景 (前端实时显示)

【全局单例】
  llm_service = LLMService() — 模块级单例，所有节点共享同一个 AsyncOpenAI 连接池
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

    OpenAI 兼容协议: 支持任何兼容 OpenAI API 的模型服务
      - Qwen (通义千问)
      - DeepSeek
      - GPT-4
      - 本地部署的 vLLM / Ollama 等
    """

    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base
        )
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None
    ) -> str:
        """非流式调用 LLM

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数（可选，默认使用配置值）

        Returns:
            LLM 完整响应内容
        """
        global _llm_call_counter
        _llm_call_counter += 1
        call_id = _llm_call_counter

        # 自动推断调用者
        caller = "unknown"
        for frame in inspect.stack():
            mod = frame.frame.f_globals.get("__name__", "")
            if "workflows.nodes" in mod or "services" in mod or "core" in mod:
                caller = mod
                break

        temp = temperature if temperature is not None else self.temperature
        input_preview = user_prompt[:200].replace("\n", "\\n")

        logger.info(
            "[LLM #%d] >>> CALL model=%s caller=%s temp=%.2f input_len=%d",
            call_id, self.model, caller, temp, len(user_prompt)
        )
        logger.debug("[LLM #%d] >>> INPUT: %s...", call_id, input_preview)

        t_start = time.time()
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temp,
            )
        except Exception:
            elapsed = time.time() - t_start
            logger.error(
                "[LLM #%d] <<< ERROR model=%s caller=%s elapsed=%.2fs",
                call_id, self.model, caller, elapsed
            )
            raise

        elapsed = time.time() - t_start
        content = response.choices[0].message.content

        # Token usage
        usage = response.usage
        if usage:
            logger.info(
                "[LLM #%d] <<< DONE model=%s caller=%s elapsed=%.2fs "
                "output_len=%d input_tokens=%d output_tokens=%d total_tokens=%d",
                call_id, self.model, caller, elapsed,
                len(content) if content else 0,
                usage.prompt_tokens, usage.completion_tokens, usage.total_tokens
            )
        else:
            logger.info(
                "[LLM #%d] <<< DONE model=%s caller=%s elapsed=%.2fs output_len=%d",
                call_id, self.model, caller, elapsed,
                len(content) if content else 0
            )

        output_preview = (content or "")[:300].replace("\n", "\\n")
        logger.debug("[LLM #%d] <<< OUTPUT: %s...", call_id, output_preview)

        return content

    async def chat_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None
    ) -> AsyncIterator[str]:
        """流式调用 LLM

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数（可选）

        Yields:
            流式响应片段
        """
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
            "[LLM #%d] >>> STREAM model=%s caller=%s temp=%.2f input_len=%d",
            call_id, self.model, caller, temp, len(user_prompt)
        )

        t_start = time.time()
        total_content = []
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
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
                call_id, self.model, caller, elapsed, len(total)
            )


# 全局 LLM 服务实例
llm_service = LLMService()


def get_llm_client() -> AsyncOpenAI:
    """获取底层 OpenAI 客户端（复用连接池）"""
    return llm_service.client

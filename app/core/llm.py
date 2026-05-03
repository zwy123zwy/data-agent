"""
统一 LLM 服务
支持流式与非流式调用，合并原 streaming_llm.py
"""
from typing import Optional, AsyncIterator
from openai import AsyncOpenAI
from .config import settings
import logging

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务封装 — 统一流式与非流式调用"""

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
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature if temperature is not None else self.temperature,
        )
        return response.choices[0].message.content

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
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature if temperature is not None else self.temperature,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise


# 全局 LLM 服务实例
llm_service = LLMService()


def get_llm_client() -> AsyncOpenAI:
    """获取底层 OpenAI 客户端（复用连接池）"""
    return llm_service.client

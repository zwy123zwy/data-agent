"""
流式 LLM 服务
支持 SSE 流式输出
"""
from typing import Optional, AsyncIterator
from openai import AsyncOpenAI
from .config import settings
import logging

logger = logging.getLogger(__name__)


class StreamingLLMService:
    """流式 LLM 服务"""

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
        """
        非流式调用（阻塞式）

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数

        Returns:
            完整响应
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature or self.temperature,
            stream=False
        )

        return response.choices[0].message.content

    async def chat_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None
    ) -> AsyncIterator[str]:
        """
        流式调用

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数

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
                temperature=temperature or self.temperature,
                stream=True
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise


# 全局实例
streaming_llm_service = StreamingLLMService()


def get_llm_client() -> AsyncOpenAI:
    """获取 OpenAI 客户端（用于其他服务）"""
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_api_base
    )

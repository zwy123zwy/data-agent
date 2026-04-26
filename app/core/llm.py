from typing import Optional
from openai import AsyncOpenAI
from ..core.config import settings


class LLMService:
    """LLM 服务封装"""

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
        调用 LLM 进行对话

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数（可选）

        Returns:
            LLM 响应内容
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=temperature or self.temperature
        )

        return response.choices[0].message.content


# 全局 LLM 服务实例
llm_service = LLMService()


def get_llm_client() -> AsyncOpenAI:
    """获取底层 OpenAI 客户端（兼容旧调用方）"""
    return llm_service.client

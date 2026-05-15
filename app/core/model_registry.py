"""
模型注册表服务 — LLM 模型的动态管理和热切换

【热切换机制】
  1. 用户 POST /api/model-config/activate/{id}
  2. 控制器调用 set_default_model(id)
  3. is_active=True 写入 DB + 更新内存缓存
  4. 后续 LLM 调用从缓存读取激活模型配置
  5. 无需重启服务 — 真正的热切换
"""
from typing import Dict, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ..models.model_config import ModelConfig
from ..schemas.model_config import ModelConfigCreate, ModelConfigUpdate
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)


class ModelRegistry:
    """模型注册表 — 对齐 Java AiModelRegistry"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache: Dict[str, ModelConfig] = {}

    async def _load_models(self):
        """从数据库加载模型配置"""
        result = await self.db.execute(
            select(ModelConfig).filter(
                ModelConfig.is_deleted == 0
            )
        )
        models = result.scalars().all()
        for model in models:
            key = f"{model.provider}-{model.model_name}"
            self._cache[key] = model
        logger.info(f"Loaded {len(self._cache)} models from database")

    async def register_model(self, config: ModelConfigCreate) -> ModelConfig:
        """注册模型 — 对齐 Java registerModel()"""
        # 如果设为激活，先取消同类型其他激活模型
        if config.is_active:
            await self.db.execute(
                update(ModelConfig)
                .where(
                    ModelConfig.model_type == config.model_type,
                    ModelConfig.is_active == 1,
                )
                .values(is_active=0)
            )

        data = config.model_dump()
        model = ModelConfig(**data)
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)

        key = f"{model.provider}-{model.model_name}"
        self._cache[key] = model
        logger.info(f"Registered model: {model.provider}/{model.model_name}")

        return model

    def get_model(self, key: str) -> Optional[ModelConfig]:
        """获取模型配置 (by cache key)"""
        return self._cache.get(key)

    async def get_model_by_id(self, model_id: int) -> Optional[ModelConfig]:
        """根据 ID 获取模型配置"""
        result = await self.db.execute(
            select(ModelConfig).filter(
                ModelConfig.id == model_id,
                ModelConfig.is_deleted == 0,
            )
        )
        return result.scalar_one_or_none()

    async def list_models(
        self, type: Optional[str] = None, enabled: Optional[bool] = None
    ) -> List[ModelConfig]:
        """列出模型配置"""
        query = select(ModelConfig).filter(ModelConfig.is_deleted == 0)

        if type:
            query = query.filter(ModelConfig.model_type == type.upper())
        if enabled is True:
            query = query.filter(ModelConfig.is_active == 1)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_default_model(self, model_type: str = "CHAT") -> Optional[ModelConfig]:
        """获取当前激活的模型 — 对齐 Java getActiveModel()"""
        result = await self.db.execute(
            select(ModelConfig).filter(
                ModelConfig.model_type == model_type.upper(),
                ModelConfig.is_active == 1,
                ModelConfig.is_deleted == 0,
            )
        )
        return result.scalar_one_or_none()

    async def update_model(
        self, model_id: int, update_data: ModelConfigUpdate
    ) -> Optional[ModelConfig]:
        """更新模型配置 — 对齐 Java updateModel()"""
        model = await self.get_model_by_id(model_id)
        if not model:
            return None

        # 如果设为激活，先取消同类型其他激活模型
        if update_data.is_active:
            await self.db.execute(
                update(ModelConfig)
                .where(
                    ModelConfig.model_type == (update_data.model_type or model.model_type).upper(),
                    ModelConfig.is_active == 1,
                    ModelConfig.id != model_id,
                )
                .values(is_active=0)
            )

        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict.pop("id", None)
        for key, value in update_dict.items():
            setattr(model, key, value)

        await self.db.commit()
        await self.db.refresh(model)

        key = f"{model.provider}-{model.model_name}"
        self._cache[key] = model
        logger.info(f"Updated model: {model.provider}/{model.model_name}")

        return model

    async def delete_model(self, model_id: int) -> bool:
        """软删除模型配置 — 对齐 Java deleteModel()"""
        model = await self.get_model_by_id(model_id)
        if not model:
            return False

        # 软删除
        model.is_deleted = 1
        model.is_active = 0

        key = f"{model.provider}-{model.model_name}"
        if key in self._cache:
            del self._cache[key]

        await self.db.commit()
        logger.info(f"Soft-deleted model: {model.provider}/{model.model_name}")
        return True

    async def set_default_model(self, model_id: int) -> Optional[ModelConfig]:
        """激活模型 — 对齐 Java activateModel()"""
        model = await self.get_model_by_id(model_id)
        if not model:
            return None

        # 取消同类型的其他激活模型
        await self.db.execute(
            update(ModelConfig)
            .where(
                ModelConfig.model_type == model.model_type,
                ModelConfig.is_active == 1,
                ModelConfig.id != model_id,
            )
            .values(is_active=0)
        )

        model.is_active = 1
        await self.db.commit()
        await self.db.refresh(model)

        key = f"{model.provider}-{model.model_name}"
        self._cache[key] = model
        logger.info(f"Activated model: {model.provider}/{model.model_name}")

        return model

    async def test_model(self, model_id: int, prompt: str = "Hello, how are you?") -> Dict:
        """测试已保存的模型"""
        model = await self.get_model_by_id(model_id)
        if not model:
            return {"success": False, "error": "Model not found"}

        return await self._do_test(
            api_key=model.api_key,
            base_url=model.base_url,
            model_name=model.model_name,
            temperature=model.temperature,
            max_tokens=model.max_tokens or 100,
            prompt=prompt,
        )

    async def test_model_with_config(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        model_type: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt: Optional[str] = None,
    ) -> Dict:
        """测试模型配置 (无需预存) — 对齐 Java POST /api/model-config/test"""
        if not api_key or not model_name:
            return {"success": False, "error": "apiKey 和 modelName 不能为空"}

        return await self._do_test(
            api_key=api_key,
            base_url=base_url or "",
            model_name=model_name,
            temperature=temperature or 0.0,
            max_tokens=max_tokens or 100,
            prompt=prompt or "Hello, how are you?",
        )

    async def _do_test(
        self,
        api_key: str,
        base_url: str,
        model_name: str,
        temperature: float,
        max_tokens: int,
        prompt: str,
    ) -> Dict:
        """执行实际的模型测试调用"""
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return {
                "success": True,
                "response": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                },
            }
        except Exception as e:
            logger.error(f"Model test failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_client(
        self, model_type: str = "CHAT"
    ) -> OpenAI:
        """创建 LLM 客户端 (从缓存获取激活模型) — 对齐 Java createClient()"""
        model = None
        for m in self._cache.values():
            if m.model_type == model_type.upper() and m.is_active == 1 and m.is_deleted == 0:
                model = m
                break

        if not model:
            raise ValueError(f"No active model found for type: {model_type}")

        return OpenAI(api_key=model.api_key, base_url=model.base_url)

    def get_model_config(self, model_type: str = "CHAT") -> Optional[ModelConfig]:
        """获取激活的模型配置"""
        for m in self._cache.values():
            if m.model_type == model_type.upper() and m.is_active == 1 and m.is_deleted == 0:
                return m
        return None


# 全局模型注册表实例
_registry: Optional[ModelRegistry] = None


def get_model_registry(db: AsyncSession) -> ModelRegistry:
    """获取模型注册表实例"""
    global _registry
    if _registry is None:
        _registry = ModelRegistry(db)
    return _registry

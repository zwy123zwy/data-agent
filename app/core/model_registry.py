"""
模型注册表服务
支持多模型管理和动态切换
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
    """模型注册表"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache: Dict[str, ModelConfig] = {}

    async def _load_models(self):
        """从数据库加载模型配置"""
        result = await self.db.execute(
            select(ModelConfig).filter(ModelConfig.enabled == True)
        )
        models = result.scalars().all()
        for model in models:
            self._cache[model.name] = model
        logger.info(f"Loaded {len(self._cache)} models from database")

    # 需要存入 metadata 的扩展字段
    _EXTRA_FIELDS = {
        "completions_path", "embeddings_path",
        "proxy_enabled", "proxy_host", "proxy_port",
        "proxy_username", "proxy_password",
    }

    # DB 列名 (可用于 ModelConfig 构造)
    _DB_FIELDS = {
        "name", "type", "provider", "model_id", "api_key", "api_base",
        "temperature", "max_tokens", "enabled", "is_default", "metadata_",
    }

    @classmethod
    def _split_extra_fields(cls, data: Dict) -> Dict:
        """将扩展字段提取到 metadata_ 中"""
        extra = {}
        for key in list(data.keys()):
            if key in cls._EXTRA_FIELDS and data[key] is not None:
                extra[key] = data.pop(key)
            elif key in cls._EXTRA_FIELDS:
                data.pop(key, None)
        if "metadata" in data:
            data["metadata_"] = data.pop("metadata")
        if extra:
            existing_meta = data.get("metadata_") or {}
            if isinstance(existing_meta, dict):
                existing_meta.update(extra)
                data["metadata_"] = existing_meta
            else:
                data["metadata_"] = extra
        return data

    async def register_model(self, config: ModelConfigCreate) -> ModelConfig:
        """注册模型"""
        # 如果设置为默认，先取消其他默认模型
        if config.is_default:
            await self.db.execute(
                update(ModelConfig)
                .where(ModelConfig.type == config.type, ModelConfig.is_default == True)
                .values(is_default=False)
            )

        # 创建模型配置 — 过滤掉非 DB 字段
        data = config.model_dump()
        data = self._split_extra_fields(data)
        # 移除不属于 DB 列的键
        data = {k: v for k, v in data.items() if k in self._DB_FIELDS}
        model = ModelConfig(**data)
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)

        # 更新缓存
        self._cache[model.name] = model
        logger.info(f"Registered model: {model.name}")

        return model

    def get_model(self, name: str) -> Optional[ModelConfig]:
        """获取模型配置"""
        return self._cache.get(name)

    async def get_model_by_id(self, model_id: int) -> Optional[ModelConfig]:
        """根据 ID 获取模型配置"""
        result = await self.db.execute(
            select(ModelConfig).filter(ModelConfig.id == model_id)
        )
        model = result.scalar_one_or_none()
        return model

    async def list_models(self, type: Optional[str] = None, enabled: Optional[bool] = None) -> List[ModelConfig]:
        """列出模型配置"""
        query = select(ModelConfig)

        if type:
            query = query.filter(ModelConfig.type == type)
        if enabled is not None:
            query = query.filter(ModelConfig.enabled == enabled)

        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_default_model(self, type: str = "chat") -> Optional[ModelConfig]:
        """获取默认模型"""
        result = await self.db.execute(
            select(ModelConfig).filter(
                ModelConfig.type == type,
                ModelConfig.is_default == True,
                ModelConfig.enabled == True
            )
        )
        model = result.scalar_one_or_none()
        return model

    async def update_model(self, model_id: int, update_data: ModelConfigUpdate) -> Optional[ModelConfig]:
        """更新模型配置"""
        model = await self.get_model_by_id(model_id)
        if not model:
            return None

        # 如果设置为默认，先取消其他默认模型
        if update_data.is_default:
            await self.db.execute(
                update(ModelConfig)
                .where(
                    ModelConfig.type == model.type,
                    ModelConfig.is_default == True,
                    ModelConfig.id != model_id
                )
                .values(is_default=False)
            )

        # 更新字段
        update_dict = update_data.model_dump(exclude_unset=True)
        update_dict.pop("id", None)  # 不更新 id 字段
        update_dict = self._split_extra_fields(update_dict)
        update_dict = {k: v for k, v in update_dict.items() if k in self._DB_FIELDS}
        for key, value in update_dict.items():
            setattr(model, key, value)

        await self.db.commit()
        await self.db.refresh(model)

        # 更新缓存
        self._cache[model.name] = model
        logger.info(f"Updated model: {model.name}")

        return model

    async def delete_model(self, model_id: int) -> bool:
        """删除模型配置"""
        model = await self.get_model_by_id(model_id)
        if not model:
            return False

        # 从缓存中移除
        if model.name in self._cache:
            del self._cache[model.name]

        await self.db.delete(model)
        await self.db.commit()
        logger.info(f"Deleted model: {model.name}")

        return True

    async def set_default_model(self, model_id: int) -> Optional[ModelConfig]:
        """设置默认模型"""
        model = await self.get_model_by_id(model_id)
        if not model:
            return None

        # 取消同类型的其他默认模型
        await self.db.execute(
            update(ModelConfig)
            .where(
                ModelConfig.type == model.type,
                ModelConfig.is_default == True,
                ModelConfig.id != model_id
            )
            .values(is_default=False)
        )

        # 设置为默认
        model.is_default = True
        await self.db.commit()
        await self.db.refresh(model)

        # 更新缓存
        self._cache[model.name] = model
        logger.info(f"Set default model: {model.name}")

        return model

    async def test_model(self, model_id: int, prompt: str = "Hello, how are you?") -> Dict:
        """测试已保存的模型"""
        model = await self.get_model_by_id(model_id)
        if not model:
            return {"success": False, "error": "Model not found"}

        return await self._do_test(
            api_key=model.api_key,
            api_base=model.api_base,
            model_id=model.model_id,
            temperature=model.temperature,
            max_tokens=model.max_tokens or 100,
            prompt=prompt,
        )

    async def test_model_with_config(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
        model_id: Optional[str] = None,
        model_type: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        prompt: Optional[str] = None,
    ) -> Dict:
        """测试模型配置 (无需预存) — 对齐 Java POST /api/model-config/test"""
        if not api_key or not model_id:
            return {"success": False, "error": "apiKey 和 modelName 不能为空"}

        return await self._do_test(
            api_key=api_key,
            api_base=api_base or "",
            model_id=model_id,
            temperature=temperature or 0.0,
            max_tokens=max_tokens or 100,
            prompt=prompt or "Hello, how are you?",
        )

    async def _do_test(
        self,
        api_key: str,
        api_base: str,
        model_id: str,
        temperature: float,
        max_tokens: int,
        prompt: str,
    ) -> Dict:
        """执行实际的模型测试调用"""
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=api_base
            )

            response = client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )

            return {
                "success": True,
                "response": response.choices[0].message.content,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            }
        except Exception as e:
            logger.error(f"Model test failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def create_client(self, model_name: Optional[str] = None, model_type: str = "chat") -> OpenAI:
        """创建 LLM 客户端（同步方法，从缓存获取）"""
        if model_name:
            model = self.get_model(model_name)
        else:
            # 从缓存中查找默认模型
            model = None
            for m in self._cache.values():
                if m.type == model_type and m.is_default and m.enabled:
                    model = m
                    break

        if not model:
            raise ValueError(f"Model not found: {model_name or 'default'}")

        return OpenAI(
            api_key=model.api_key,
            base_url=model.api_base
        )

    def get_model_config(self, model_name: Optional[str] = None, model_type: str = "chat") -> Optional[ModelConfig]:
        """获取模型配置（用于创建客户端）"""
        if model_name:
            return self.get_model(model_name)
        else:
            # 从缓存中查找默认模型
            for m in self._cache.values():
                if m.type == model_type and m.is_default and m.enabled:
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

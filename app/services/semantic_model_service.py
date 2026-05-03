"""
SemanticModel Service
语义模型服务 - 业务术语映射管理
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from typing import List, Optional
from ..models.semantic_model import SemanticModel
from ..schemas.semantic_model import SemanticModelCreate, SemanticModelUpdate, SemanticModelSearchRequest
import logging

logger = logging.getLogger(__name__)


class SemanticModelService:
    """语义模型服务"""

    @staticmethod
    async def create_semantic_model(
        db: AsyncSession,
        agent_id: int,
        model_data: SemanticModelCreate
    ) -> SemanticModel:
        """
        创建语义模型

        Args:
            db: 数据库会话
            agent_id: Agent ID
            model_data: 语义模型数据

        Returns:
            创建的语义模型对象
        """
        semantic_model = SemanticModel(
            agent_id=agent_id,
            datasource_id=model_data.datasource_id,
            table_name=model_data.table_name,
            column_name=model_data.column_name,
            business_name=model_data.business_name,
            business_description=model_data.description,
            synonyms=",".join(model_data.synonyms) if model_data.synonyms else None,
            column_comment=model_data.column_comment,
            data_type=model_data.data_type,
            status=1,
            sample_values=model_data.sample_values,
            metadata_=model_data.metadata
        )

        db.add(semantic_model)
        await db.commit()
        await db.refresh(semantic_model)

        logger.info(f"Created semantic model {semantic_model.id} for agent {agent_id}")
        return semantic_model

    @staticmethod
    async def get_semantic_model(db: AsyncSession, model_id: int) -> Optional[SemanticModel]:
        """获取语义模型详情"""
        result = await db.execute(
            select(SemanticModel).where(SemanticModel.id == model_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list_semantic_models(
        db: AsyncSession,
        agent_id: int,
        datasource_id: Optional[int] = None,
        table_name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> tuple[List[SemanticModel], int]:
        """
        列出语义模型

        Returns:
            (语义模型列表, 总数)
        """
        # 构建查询条件
        conditions = [SemanticModel.agent_id == agent_id]
        if datasource_id:
            conditions.append(SemanticModel.datasource_id == datasource_id)
        if table_name:
            conditions.append(SemanticModel.table_name == table_name)

        # 查询总数
        count_result = await db.execute(select(func.count(SemanticModel.id)).where(and_(*conditions)))
        total = count_result.scalar() or 0

        # 查询列表
        result = await db.execute(
            select(SemanticModel)
            .where(and_(*conditions))
            .order_by(SemanticModel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        models = result.scalars().all()

        return list(models), total

    @staticmethod
    async def update_semantic_model(
        db: AsyncSession,
        model_id: int,
        model_data: SemanticModelUpdate
    ) -> Optional[SemanticModel]:
        """更新语义模型"""
        semantic_model = await SemanticModelService.get_semantic_model(db, model_id)
        if not semantic_model:
            return None

        # 更新字段
        update_data = model_data.model_dump(exclude_unset=True)
        if "metadata" in update_data:
            update_data["metadata_"] = update_data.pop("metadata")
        for field, value in update_data.items():
            setattr(semantic_model, field, value)

        await db.commit()
        await db.refresh(semantic_model)

        logger.info(f"Updated semantic model {model_id}")
        return semantic_model

    @staticmethod
    async def delete_semantic_model(db: AsyncSession, model_id: int) -> bool:
        """删除语义模型"""
        semantic_model = await SemanticModelService.get_semantic_model(db, model_id)
        if not semantic_model:
            return False

        await db.delete(semantic_model)
        await db.commit()

        logger.info(f"Deleted semantic model {model_id}")
        return True

    @staticmethod
    async def search_semantic_models(
        db: AsyncSession,
        agent_id: int,
        search_request: SemanticModelSearchRequest
    ) -> List[SemanticModel]:
        """
        搜索语义模型

        根据业务名称或同义词搜索

        Args:
            db: 数据库会话
            agent_id: Agent ID
            search_request: 搜索请求

        Returns:
            匹配的语义模型列表
        """
        query_text = search_request.query.lower()

        # 构建基础条件
        conditions = [SemanticModel.agent_id == agent_id]
        if search_request.datasource_id:
            conditions.append(SemanticModel.datasource_id == search_request.datasource_id)
        if search_request.table_name:
            conditions.append(SemanticModel.table_name == search_request.table_name)

        # 查询所有符合基础条件的模型
        result = await db.execute(
            select(SemanticModel).where(and_(*conditions))
        )
        all_models = result.scalars().all()

        # 在内存中过滤匹配的模型
        matched_models = []
        for model in all_models:
            # 检查业务名称
            if query_text in model.business_name.lower():
                matched_models.append(model)
                continue

            # 检查同义词（逗号分隔的字符串）
            if model.synonyms:
                synonyms_list = [s.strip() for s in model.synonyms.split(",")]
                for synonym in synonyms_list:
                    if query_text in synonym.lower():
                        matched_models.append(model)
                        break

        logger.info(f"Search returned {len(matched_models)} semantic models for agent {agent_id}")
        return matched_models

    @staticmethod
    async def get_table_semantic_info(
        db: AsyncSession,
        agent_id: int,
        datasource_id: int,
        table_name: str
    ) -> str:
        """
        获取表的语义信息（用于 LLM）

        Args:
            db: 数据库会话
            agent_id: Agent ID
            datasource_id: 数据源ID
            table_name: 表名

        Returns:
            格式化的语义信息文本
        """
        result = await db.execute(
            select(SemanticModel).where(
                and_(
                    SemanticModel.agent_id == agent_id,
                    SemanticModel.datasource_id == datasource_id,
                    SemanticModel.table_name == table_name
                )
            )
        )
        models = result.scalars().all()

        if not models:
            return ""

        # 格式化为文本
        semantic_info = f"\n表 {table_name} 的业务语义:\n"

        # 表级别的语义
        table_models = [m for m in models if not m.column_name]
        if table_models:
            for model in table_models:
                semantic_info += f"  业务名称: {model.business_name}\n"
                if model.business_description:
                    semantic_info += f"  说明: {model.business_description}\n"
                if model.synonyms:
                    semantic_info += f"  同义词: {model.synonyms}\n"

        # 字段级别的语义
        column_models = [m for m in models if m.column_name]
        if column_models:
            semantic_info += f"\n  字段语义:\n"
            for model in column_models:
                semantic_info += f"    - {model.column_name} ({model.business_name})"
                if model.business_description:
                    semantic_info += f": {model.business_description}"
                if model.synonyms:
                    semantic_info += f" [同义词: {model.synonyms}]"
                semantic_info += "\n"

        return semantic_info

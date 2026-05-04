"""LogicalRelationService — 对齐 Java DatasourceService 中 logicalRelations 部分"""
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.logical_relation import LogicalRelation
from ..schemas.logical_relation import (
    LogicalRelationCreate,
    LogicalRelationUpdate,
    LogicalRelationResponse,
)


class LogicalRelationService:

    @staticmethod
    async def list_by_datasource(db: AsyncSession, datasource_id: int) -> List[LogicalRelationResponse]:
        result = await db.execute(
            select(LogicalRelation)
            .where(
                and_(
                    LogicalRelation.datasource_id == datasource_id,
                    LogicalRelation.is_deleted == 0,
                )
            )
            .order_by(LogicalRelation.created_time.desc())
        )
        return [LogicalRelationResponse.model_validate(r) for r in result.scalars().all()]

    @staticmethod
    async def create(db: AsyncSession, datasource_id: int, dto: LogicalRelationCreate) -> LogicalRelationResponse:
        lr = LogicalRelation(
            datasource_id=datasource_id,
            source_table_name=dto.source_table_name,
            source_column_name=dto.source_column_name,
            target_table_name=dto.target_table_name,
            target_column_name=dto.target_column_name,
            relation_type=dto.relation_type,
            description=dto.description,
        )
        db.add(lr)
        await db.flush()
        await db.refresh(lr)
        return LogicalRelationResponse.model_validate(lr)

    @staticmethod
    async def update(db: AsyncSession, relation_id: int, dto: LogicalRelationUpdate) -> Optional[LogicalRelationResponse]:
        result = await db.execute(
            select(LogicalRelation).where(
                and_(LogicalRelation.id == relation_id, LogicalRelation.is_deleted == 0)
            )
        )
        lr = result.scalar_one_or_none()
        if not lr:
            return None
        update_data = dto.model_dump(exclude_unset=True, by_alias=False)
        for key, value in update_data.items():
            setattr(lr, key, value)
        await db.flush()
        await db.refresh(lr)
        return LogicalRelationResponse.model_validate(lr)

    @staticmethod
    async def delete(db: AsyncSession, relation_id: int) -> bool:
        result = await db.execute(
            select(LogicalRelation).where(
                and_(LogicalRelation.id == relation_id, LogicalRelation.is_deleted == 0)
            )
        )
        lr = result.scalar_one_or_none()
        if not lr:
            return False
        lr.is_deleted = 1
        await db.flush()
        return True

    @staticmethod
    async def batch_save(
        db: AsyncSession, datasource_id: int, relations: List[LogicalRelationCreate]
    ) -> List[LogicalRelationResponse]:
        # 软删除旧的全部
        result = await db.execute(
            select(LogicalRelation).where(
                and_(LogicalRelation.datasource_id == datasource_id, LogicalRelation.is_deleted == 0)
            )
        )
        for old in result.scalars().all():
            old.is_deleted = 1

        # 创建新的
        responses = []
        for dto in relations:
            lr = LogicalRelation(
                datasource_id=datasource_id,
                source_table_name=dto.source_table_name,
                source_column_name=dto.source_column_name,
                target_table_name=dto.target_table_name,
                target_column_name=dto.target_column_name,
                relation_type=dto.relation_type,
                description=dto.description,
            )
            db.add(lr)
            await db.flush()
            await db.refresh(lr)
            responses.append(LogicalRelationResponse.model_validate(lr))

        return responses

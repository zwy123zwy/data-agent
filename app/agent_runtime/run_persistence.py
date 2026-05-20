# [阶段4] Run / Event / Artifact 持久化服务

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_runtime.context import RuntimeContext
from app.agent_runtime.events import AgentSSEEvent
from app.agent_runtime.state import RunMetrics
from app.models.agent_artifact import AgentArtifactRecord
from app.models.agent_run import AgentRun
from app.models.agent_run_event import AgentRunEvent

logger = logging.getLogger(__name__)


class RunPersistenceService:
    """[阶段4] Orchestrator 结束后写入 agent_run* 三表。"""

    @staticmethod
    async def persist_run(
        db: AsyncSession,
        *,
        ctx: RuntimeContext,
        events: list[AgentSSEEvent],
        metrics: RunMetrics | None = None,
    ) -> None:
        # 约定：工具级失败由 Explorer 等再 emit event_type=error（见 explorer_agent），
        # 不单靠 tool.result.status=error 判定整 run 失败。
        final_status = "error" if any(e.event_type == "error" for e in events) else "ok"
        summary = next(
            (e.summary for e in reversed(events) if e.event_type == "run.complete"),
            events[-1].summary if events else "",
        )

        run = AgentRun(
            id=ctx.run_id,
            agent_id=ctx.agent_id,
            thread_id=ctx.thread_id,
            mode=ctx.mode,
            status=final_status,
            user_query=ctx.user_query,
            summary=summary,
        )
        db.add(run)

        for ev in events:
            payload = ev.model_dump(by_alias=True, exclude_none=True)
            db.add(
                AgentRunEvent(
                    run_id=ctx.run_id,
                    event_type=ev.event_type or "unknown",
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
            )
            for ref in ev.artifact_refs or []:
                artifact_id = ref.get("id")
                if not artifact_id:
                    logger.warning(
                        "[阶段4] 跳过无 id 的 artifact_ref run_id=%s type=%s",
                        ctx.run_id,
                        ref.get("type"),
                    )
                    continue
                db.add(
                    AgentArtifactRecord(
                        id=artifact_id,
                        run_id=ctx.run_id,
                        artifact_type=ref.get("type", "unknown"),
                        content_json=None,
                    )
                )

        await db.commit()
        logger.info("[阶段4] 已持久化 run_id=%s events=%d", ctx.run_id, len(events))

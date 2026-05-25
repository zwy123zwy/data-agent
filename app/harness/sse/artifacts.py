# [阶段1] SSE artifact 引用构造（emit 与 tool 层共用）

from __future__ import annotations

from typing import Any

from app.harness.tools.base import ToolResult


def artifact_refs_from_artifacts(artifacts: list[Any]) -> list[dict[str, str]]:
    """[阶段1] 任意带 id/type 的 artifact 列表 → SSE artifactRefs。"""
    out: list[dict[str, str]] = []
    for a in artifacts:
        aid = getattr(a, "id", None)
        atype = getattr(a, "type", None)
        if aid is not None and atype is not None:
            out.append({"id": str(aid), "type": str(atype)})
    return out


def artifact_refs_from_tool_result(result: ToolResult) -> list[dict[str, str]]:
    """[阶段1] Harness ToolResult → SSE artifactRefs。"""
    return artifact_refs_from_artifacts(result.artifacts)

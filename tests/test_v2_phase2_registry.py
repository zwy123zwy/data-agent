# [阶段2] 12 Tool 注册表测试

from app.agent_runtime.tools.build_registry import build_full_registry


def test_full_registry_has_twelve_tools():
    reg = build_full_registry()
    names = reg.list_names()
    assert len(names) == 12
    assert "search_knowledge" in names
    assert "generate_report" in names
    assert "ask_human" in names

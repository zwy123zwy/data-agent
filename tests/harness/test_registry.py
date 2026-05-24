# [阶段2] Harness Tool 注册表

from app.harness.tools.registry import build_harness_registry, list_for_mode


def test_harness_registry_four_tools():
    reg = build_harness_registry()
    assert set(reg.list_names()) == {
        "search_knowledge",
        "inspect_schema",
        "generate_sql",
        "execute_sql",
    }


def test_list_for_mode_smart_query():
    assert list_for_mode("smart_query") == [
        "search_knowledge",
        "inspect_schema",
        "generate_sql",
        "execute_sql",
    ]

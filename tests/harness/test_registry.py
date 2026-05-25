# [阶段4] Harness Tool 注册表

from app.harness.tools.registry import build_harness_registry, list_descriptors
from app.harness.types.context import DatasetRef, RuntimeContext


def test_harness_registry_four_tools():
    reg = build_harness_registry()
    assert set(reg.list_names()) == {
        "search_knowledge",
        "inspect_schema",
        "generate_sql",
        "execute_sql",
    }


def test_list_descriptors_matches_registered_tools():
    ctx = RuntimeContext(
        run_id="r",
        thread_id="t",
        agent_id=1,
        user_query="q",
        mode="smart_query",
        datasets=[
            DatasetRef(
                datasource_id=1,
                datasource_name="ds",
                database_name="db",
                table_name="t",
            )
        ],
    )
    assert len(list_descriptors(ctx)) == 4

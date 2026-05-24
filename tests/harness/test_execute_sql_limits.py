# [阶段2] execute_sql 行数 LIMIT（M2.5）

from app.harness.tools.execute_sql import _apply_row_limit, _max_result_rows
from app.harness.types.context import Permissions, RuntimeContext


def test_apply_row_limit_appends_limit():
    sql = "SELECT * FROM orders"
    out = _apply_row_limit(sql, 100)
    assert "LIMIT 100" in out.upper()


def test_apply_row_limit_skips_when_present():
    sql = "SELECT * FROM orders LIMIT 50"
    out = _apply_row_limit(sql, 100)
    assert out.upper().count("LIMIT") == 1


def test_max_result_rows_from_permissions():
    ctx = RuntimeContext(
        run_id="r",
        thread_id="t",
        agent_id=1,
        user_query="q",
        mode="smart_query",
        permissions=Permissions(max_sql_result_rows=500),
    )
    assert _max_result_rows(ctx) == 500

"""P0 短板修复测试 — SQL 安全校验 + Docker 执行器 + Checkpointer 持久化

覆盖:
  1. SQL 安全校验 (20+ 用例)
  2. Docker 执行器 (5 用例)
  3. Checkpointer 持久化 (3 用例)
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

from app.core.sql_validator import validate_sql_safety, _strip_strings_and_comments


# =========================================================================
# 1. SQL 安全校验测试
# =========================================================================

class TestSQLValidatorBasics:
    """基本校验功能"""

    def test_empty_sql(self):
        assert validate_sql_safety("") == "SQL 语句为空"
        assert validate_sql_safety("   ") == "SQL 语句为空"

    def test_valid_select_simple(self):
        assert validate_sql_safety("SELECT * FROM users") is None

    def test_valid_select_with_columns(self):
        assert validate_sql_safety("SELECT id, name, email FROM users WHERE status = 1") is None

    def test_valid_select_with_join(self):
        sql = "SELECT u.name, o.amount FROM users u JOIN orders o ON u.id = o.user_id"
        assert validate_sql_safety(sql) is None

    def test_valid_select_with_subquery(self):
        sql = "SELECT * FROM (SELECT id FROM users WHERE status = 1) AS active_users"
        assert validate_sql_safety(sql) is None

    def test_valid_with_cte(self):
        sql = "WITH active AS (SELECT id FROM users WHERE status=1) SELECT * FROM active"
        assert validate_sql_safety(sql) is None

    def test_valid_explain(self):
        assert validate_sql_safety("EXPLAIN SELECT * FROM users") is None

    def test_valid_describe(self):
        assert validate_sql_safety("DESCRIBE users") is None
        assert validate_sql_safety("DESC users") is None

    def test_valid_show(self):
        assert validate_sql_safety("SHOW TABLES") is None
        assert validate_sql_safety("SHOW COLUMNS FROM users") is None

    def test_case_insensitive(self):
        assert validate_sql_safety("select * from users") is None
        assert validate_sql_safety("Select Id From Users") is None
        assert validate_sql_safety("SELECT * FROM USERS") is None


class TestSQLValidatorBlockDDL:
    """拦截 DDL 语句"""

    def test_block_create_table(self):
        err = validate_sql_safety("CREATE TABLE test (id INT)")
        assert err is not None
        assert "CREATE" in err

    def test_block_alter_table(self):
        err = validate_sql_safety("ALTER TABLE users ADD COLUMN age INT")
        assert err is not None
        assert "ALTER" in err

    def test_block_drop_table(self):
        err = validate_sql_safety("DROP TABLE users")
        assert err is not None
        assert "DROP" in err

    def test_block_truncate(self):
        err = validate_sql_safety("TRUNCATE TABLE users")
        assert err is not None
        assert "TRUNCATE" in err


class TestSQLValidatorBlockDML:
    """拦截 DML 语句"""

    def test_block_insert(self):
        err = validate_sql_safety("INSERT INTO users VALUES (1, 'test')")
        assert err is not None
        assert "INSERT" in err

    def test_block_update(self):
        err = validate_sql_safety("UPDATE users SET name = 'hacked'")
        assert err is not None
        assert "UPDATE" in err

    def test_block_delete(self):
        err = validate_sql_safety("DELETE FROM users")
        assert err is not None
        assert "DELETE" in err

    def test_block_replace(self):
        err = validate_sql_safety("REPLACE INTO users VALUES (1, 'test')")
        assert err is not None
        assert "REPLACE" in err

    def test_block_merge(self):
        err = validate_sql_safety("MERGE INTO users USING source ON users.id = source.id")
        assert err is not None
        assert "MERGE" in err


class TestSQLValidatorBlockDangerous:
    """拦截危险操作"""

    def test_block_into_outfile(self):
        err = validate_sql_safety("SELECT * FROM users INTO OUTFILE '/tmp/data.txt'")
        assert err is not None

    def test_block_grant(self):
        err = validate_sql_safety("GRANT SELECT ON users TO 'test'")
        assert err is not None

    def test_block_multiple_statements(self):
        """分号堆叠注入: SELECT 后跟 DROP"""
        err = validate_sql_safety("SELECT * FROM users; DROP TABLE users")
        assert err is not None
        # 可能先命中 DROP 关键字，也可能命中分号检查
        assert "DROP" in err or "分号" in err or "多条" in err

    def test_block_sleep_injection(self):
        err = validate_sql_safety("SELECT SLEEP(10) FROM users")
        assert err is not None
        assert "SLEEP" in err

    def test_block_execute(self):
        err = validate_sql_safety("EXECUTE sp_dangerous")
        assert err is not None


class TestSQLValidatorEdgeCases:
    """边界情况"""

    def test_string_literal_contains_dangerous_keyword(self):
        """字符串中包含 'DROP' 不应触发拦截"""
        assert validate_sql_safety("SELECT * FROM users WHERE name = 'DROP TABLE'") is None

    def test_comment_contains_dangerous_keyword(self):
        """注释中包含危险关键字不应触发"""
        assert validate_sql_safety("SELECT * FROM users -- DROP TABLE users") is None

    def test_block_comment_contains_keyword(self):
        """块注释中的危险关键字不应触发"""
        sql = "SELECT * FROM users /* DROP TABLE */ WHERE status=1"
        assert validate_sql_safety(sql) is None

    def test_column_named_like_keyword(self):
        """列名包含 'update' 子串不应误判"""
        sql = "SELECT updated_at, deleted_flag FROM users"
        assert validate_sql_safety(sql) is None

    def test_non_allowed_prefix(self):
        err = validate_sql_safety("ANALYZE TABLE users")
        assert err is not None
        assert "ANALYZE" in err

    def test_sql_with_newlines_and_tabs(self):
        sql = """SELECT id, name
        FROM users
        WHERE status = 1"""
        assert validate_sql_safety(sql) is None


class TestStripStringsAndComments:
    """字符串和注释剥离辅助函数"""

    def test_strip_single_line_comment(self):
        result = _strip_strings_and_comments("SELECT * -- comment")
        assert "comment" not in result

    def test_strip_block_comment(self):
        result = _strip_strings_and_comments("SELECT /* block */ *")
        assert "block" not in result

    def test_strip_string_literal(self):
        result = _strip_strings_and_comments("SELECT 'DROP TABLE'")
        assert "DROP TABLE" not in result
        assert "''" in result


# =========================================================================
# 2. Docker 执行器测试
# =========================================================================

class TestDockerExecutor:
    """Docker 执行器 — 不依赖实际 Docker daemon 的单元测试"""

    @pytest.mark.asyncio
    async def test_docker_not_installed(self):
        """Docker 未安装时返回错误"""
        from app.core.code_executor import DockerExecutor
        executor = DockerExecutor(timeout=30, memory="128M")

        with patch("app.core.code_executor.shutil.which", return_value=None):
            result = await executor.execute("print('hello')")
            assert result.success is False
            assert "未安装" in result.error or "PATH" in result.error

    @pytest.mark.asyncio
    async def test_docker_not_found(self):
        """docker 命令不存在"""
        from app.core.code_executor import DockerExecutor
        executor = DockerExecutor(timeout=30, memory="128M")

        with patch("app.core.code_executor.shutil.which", return_value="/usr/bin/docker"):
            with patch("app.core.code_executor.subprocess.run", side_effect=FileNotFoundError):
                result = await executor.execute("print('hello')")
                assert result.success is False
                assert "不可用" in result.error or "PATH" in result.error

    @pytest.mark.asyncio
    async def test_docker_successful_execution(self):
        """模拟 Docker 成功执行"""
        from app.core.code_executor import DockerExecutor, ExecutionResult
        executor = DockerExecutor(timeout=30, memory="128M")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "hello world\n"
        mock_result.stderr = ""

        with patch("app.core.code_executor.shutil.which", return_value="/usr/bin/docker"):
            with patch("app.core.code_executor.subprocess.run", return_value=mock_result):
                result = await executor.execute("print('hello world')")
                assert result.success is True
                assert "hello world" in result.output

    @pytest.mark.asyncio
    async def test_docker_execution_failure(self):
        """模拟 Docker 执行失败"""
        from app.core.code_executor import DockerExecutor
        executor = DockerExecutor(timeout=30, memory="128M")

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "NameError: name 'x' is not defined"

        with patch("app.core.code_executor.shutil.which", return_value="/usr/bin/docker"):
            with patch("app.core.code_executor.subprocess.run", return_value=mock_result):
                result = await executor.execute("print(x)")
                assert result.success is False
                assert "NameError" in result.error

    @pytest.mark.asyncio
    async def test_docker_oom_detection(self):
        """Docker OOM (exit code 137) 检测"""
        from app.core.code_executor import DockerExecutor
        executor = DockerExecutor(timeout=30, memory="128M")

        mock_result = MagicMock()
        mock_result.returncode = 137
        mock_result.stdout = ""
        mock_result.stderr = "Killed"

        with patch("app.core.code_executor.shutil.which", return_value="/usr/bin/docker"):
            with patch("app.core.code_executor.subprocess.run", return_value=mock_result):
                result = await executor.execute("x = [1]*1000000000")
                assert result.success is False
                assert "OOM" in result.error or "内存" in result.error

    @pytest.mark.asyncio
    async def test_docker_with_data_injection(self):
        """Docker 执行器注入 JSON 数据"""
        from app.core.code_executor import DockerExecutor
        executor = DockerExecutor(timeout=30, memory="128M")

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "3\n"
        mock_result.stderr = ""

        data = [{"name": "Alice", "sales": 100}, {"name": "Bob", "sales": 200}]

        with patch("app.core.code_executor.shutil.which", return_value="/usr/bin/docker"):
            with patch("app.core.code_executor.subprocess.run", return_value=mock_result):
                result = await executor.execute(
                    "total = sum(row['sales'] for row in sql_result)\n"
                    "print(total)",
                    data=data,
                )
                assert result.success is True

    def test_executor_factory_docker(self):
        """工厂方法创建 Docker 执行器"""
        from app.core.code_executor import ExecutorFactory, DockerExecutor
        executor = ExecutorFactory.create("docker")
        assert isinstance(executor, DockerExecutor)

    def test_executor_factory_local(self):
        from app.core.code_executor import ExecutorFactory, LocalExecutor
        executor = ExecutorFactory.create("local")
        assert isinstance(executor, LocalExecutor)

    def test_executor_factory_unknown(self):
        from app.core.code_executor import ExecutorFactory
        with pytest.raises(ValueError):
            ExecutorFactory.create("unknown")


# =========================================================================
# 3. Checkpointer 持久化测试
# =========================================================================

class TestCheckpointerConfig:
    """Checkpointer 配置切换测试"""

    def test_config_default_is_sqlite(self):
        """默认配置为 sqlite"""
        from app.core.config import settings
        assert settings.checkpointer_type == "sqlite"
        assert settings.checkpointer_db_path == "checkpoints.db"

    @pytest.mark.asyncio
    async def test_compiled_workflow_exists(self):
        """验证 compiled_workflow 已编译并可用"""
        from app.workflows.graph import compiled_workflow
        assert compiled_workflow is not None

    def test_memory_saver_import(self):
        """MemorySaver 仍然可用"""
        from langgraph.checkpoint.memory import MemorySaver
        saver = MemorySaver()
        assert saver is not None

    def test_sqlite_saver_import(self):
        """SqliteSaver 可用"""
        from langgraph.checkpoint.sqlite import SqliteSaver
        # 使用 :memory: 不创建文件
        saver = SqliteSaver.from_conn_string(":memory:")
        assert saver is not None


# =========================================================================
# 4. SQL 校验器在 sql_execute 中集成测试
# =========================================================================

class TestSQLValidationIntegration:
    """验证 SQL 校验已集成到 sql_execute_node"""

    def test_sql_validator_imported_in_sql_execute(self):
        """确认 validate_sql_safety 已在 sql_execute_node 中导入"""
        from app.workflows.nodes.sql_execute import validate_sql_safety
        assert validate_sql_safety is not None

    @pytest.mark.asyncio
    async def test_sql_execute_rejects_dangerous_sql(self):
        """sql_execute_node 应拒绝危险 SQL"""
        from app.workflows.nodes.sql_execute import sql_execute_node

        state = {
            "agent_id": 1,
            "generated_sql": "DROP TABLE users; SELECT * FROM users",
            "plan_current_step": 1,
        }
        result = await sql_execute_node(state)
        assert "sql_error" in result
        assert "安全校验" in result.get("sql_error", "")

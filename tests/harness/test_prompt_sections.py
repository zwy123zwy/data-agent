# [阶段1] Harness prompt sections 单测

from app.harness.prompts.sections import (
    build_layered_user_prompt,
    format_conversation_history,
    format_preflight_environment,
)
from app.harness.types.preflight import PreflightSnapshot


def test_format_conversation_history_truncates_assistant():
    long_assistant = "澄清" + "x" * 200
    out = format_conversation_history(
        [
            {"role": "user", "content": "查销售"},
            {"role": "assistant", "content": long_assistant},
        ],
    )
    assert "查销售" in out
    assert "x" * 150 not in out


def test_build_layered_user_prompt_skips_empty_prefix():
    out = build_layered_user_prompt(
        user_query="你好",
        prefix_sections=["", "  ", "## 环境\n- ok\n"],
    )
    assert "## 环境" in out
    assert out.endswith("你好")


def test_format_preflight_environment():
    pre = PreflightSnapshot(agent_ok=True, has_datasource=True)
    out = format_preflight_environment(pre)
    assert "有激活数据源" in out

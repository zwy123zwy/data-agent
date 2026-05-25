# [阶段1] Harness PromptLoader 单测

import pytest

from app.harness.prompts import (
    HarnessPromptKey,
    clear_prompt_cache,
    get_system_prompt_sync,
    load_prompt_file,
)
from app.harness.prompts.keys import db_prompt_type


def test_load_chitchat_file():
    clear_prompt_cache()
    text = load_prompt_file(HarnessPromptKey.CHITCHAT)
    assert len(text.strip()) > 0


def test_db_prompt_type_naming():
    assert db_prompt_type(HarnessPromptKey.CHITCHAT) == "harness-chitchat"
    assert db_prompt_type(HarnessPromptKey.TOOL_PICKER) == "harness-tool-picker"


def test_run_override_replaces_base():
    clear_prompt_cache()
    custom = "完全自定义 Tool Picker 提示"
    out = get_system_prompt_sync(
        HarnessPromptKey.TOOL_PICKER,
        overrides={"tool_picker": custom},
    )
    assert out == custom


def test_missing_file_raises(monkeypatch, tmp_path):
    from app.core.config import settings

    monkeypatch.setattr(settings, "harness_prompts_dir", str(tmp_path))
    clear_prompt_cache()
    with pytest.raises(FileNotFoundError):
        load_prompt_file(HarnessPromptKey.CHITCHAT)

# [阶段2] harness 包静态约束：不得依赖 V1 业务链或 agent_runtime 契约

import ast
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS = ROOT / "app" / "harness"

_FORBIDDEN_PREFIXES = ("app.workflows", "app.agent_runtime")


def _scan_harness_py_files() -> None:
    """[阶段2] AST 扫描 import；注释中的字样不计入。"""
    for py in HARNESS.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
                    assert not mod.startswith(_FORBIDDEN_PREFIXES), f"{py}: import {mod}"
                    assert "wrap_v1" not in mod, f"{py}: import {mod}"
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                assert not mod.startswith(_FORBIDDEN_PREFIXES), f"{py}: from {mod}"
                assert "wrap_v1" not in mod, f"{py}: from {mod}"
                for alias in node.names:
                    assert "wrap_v1" not in (alias.name or ""), f"{py}: from {mod} import {alias.name}"


def test_harness_has_no_forbidden_imports():
    patterns = (
        "wrap_v1",
        "from app\\.workflows",
        "import app\\.workflows",
        "from app\\.agent_runtime",
        "import app\\.agent_runtime",
    )
    try:
        proc = subprocess.run(
            ["rg", "-e", "|".join(patterns), str(HARNESS)],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
    except FileNotFoundError:
        _scan_harness_py_files()
        return
    if proc.returncode == 127:
        _scan_harness_py_files()
        return
    # rg 无匹配时 returncode=1
    assert proc.returncode == 1, proc.stdout or proc.stderr

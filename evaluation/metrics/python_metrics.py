"""
Python 分析评测指标 — L3 层: Python 代码质量评估

【在系统中的地位】
  评测模型生成的 Python 数据分析代码的质量。
  包括: 代码可执行率、输出正确性、代码规范度。

【指标说明】
  PER (Python Execution Rate):
    生成的 Python 代码是否能成功执行 (无语法错误、无运行时异常)

  POC (Python Output Correctness):
    执行输出是否包含预期的关键结果 (数值、字段名等)

  PQS (Python Quality Score):
    代码质量评分: 是否有必要的错误处理、是否使用向量化操作、复杂度

【模块连接】
  上游:
    - run_evaluation.py → 调用 compute_python_metrics()

  下游:
    - subprocess / Docker → 实际执行 Python 代码
    - ast (标准库) → 静态语法检查

  Java 对应:
    PythonAnalyzeNode.java + CodePoolExecutorService.java 的评测部分
"""
import ast
import re
import sys
import io
import subprocess
import tempfile
import time
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class PythonMetricsResult:
    """单条 Python 代码的评测结果"""
    test_id: int
    syntax_valid: bool = False
    execution_success: bool = False
    output_has_result: bool = False
    error_message: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0


@dataclass
class PythonEvalReport:
    """Python 评测汇总报告"""
    total: int
    syntax_pass: int = 0
    execution_pass: int = 0
    output_correct: int = 0
    avg_time_ms: float = 0
    details: List[PythonMetricsResult] = field(default_factory=list)

    @property
    def exec_rate(self) -> float:
        return self.execution_pass / self.total * 100 if self.total else 0

    @property
    def output_rate(self) -> float:
        return self.output_correct / self.total * 100 if self.total else 0


# ============================================================================
# 静态语法检查
# ============================================================================

def check_python_syntax(code: str) -> Tuple[bool, Optional[str]]:
    """静态语法检查 — 使用 Python AST 解析器

    Returns:
        (是否有效, 错误信息)
    """
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"


# ============================================================================
# 安全检查
# ============================================================================

# 危险操作黑名单
FORBIDDEN_PATTERNS = [
    r'\bos\.system\s*\(',
    r'\bsubprocess\.',
    r'\beval\s*\(',
    r'\bexec\s*\(',
    r'\b__import__\s*\(',
    r'\bopen\s*\([^)]*[\'"]w',
    r'\bshutil\.rmtree\b',
    r'\bos\.remove\s*\(',
    r'\bos\.unlink\s*\(',
    r'\bos\.rmdir\s*\(',
    r'\bimport\s+ctypes\b',
    r'\bimport\s+socket\b',
]

ALLOWED_IMPORTS = {
    'pandas', 'numpy', 'matplotlib', 'seaborn', 'scipy',
    'json', 'csv', 'datetime', 'math', 'statistics',
    'collections', 'itertools', 'functools', 'typing',
    'io', 'pathlib', 're', 'random', 'warnings',
    'sklearn', 'scipy.stats', 'plotly',
}


def check_python_safety(code: str) -> Tuple[bool, Optional[str]]:
    """安全检查 — 防止危险操作

    Returns:
        (是否安全, 违规内容)
    """
    for pattern in FORBIDDEN_PATTERNS:
        if re.search(pattern, code):
            return False, f"Forbidden pattern detected: {pattern}"
    return True, None


# ============================================================================
# 运行时执行
# ============================================================================

def execute_python_code(
    code: str,
    data_context: Optional[Dict[str, Any]] = None,
    timeout_sec: int = 30
) -> Tuple[bool, str, str, float]:
    """在隔离的 subprocess 中执行 Python 代码

    Args:
        code: Python 代码
        data_context: 数据上下文 (变量绑定，如 {"df": some_dataframe})
        timeout_sec: 超时时间

    Returns:
        (是否成功, stdout, stderr, 执行时间ms)
    """
    # 包装代码：注入数据上下文 + 捕获输出
    wrapped_code = []
    wrapped_code.append("import json, sys")
    wrapped_code.append("")
    wrapped_code.append("# ---- 注入数据上下文 ----")
    if data_context:
        for var_name, var_data in data_context.items():
            if isinstance(var_data, list):
                wrapped_code.append(f"import pandas as pd")
                wrapped_code.append(f"{var_name} = pd.DataFrame({var_data!r})")
            elif isinstance(var_data, str):
                wrapped_code.append(f"{var_name} = {var_data!r}")
            else:
                wrapped_code.append(f"{var_name} = {var_data!r}")
    wrapped_code.append("")
    wrapped_code.append("# ---- 用户代码 ----")
    wrapped_code.append(code)
    wrapped_code.append("")
    wrapped_code.append("# ---- 输出结果 ----")
    wrapped_code.append("print('__EXEC_SUCCESS__')")

    full_code = "\n".join(wrapped_code)

    start = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-c", full_code],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        success = result.returncode == 0 and "__EXEC_SUCCESS__" in result.stdout
        return success, result.stdout, result.stderr, elapsed_ms
    except subprocess.TimeoutExpired:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return False, "", f"Execution timed out after {timeout_sec}s", elapsed_ms
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return False, "", str(e), elapsed_ms


# ============================================================================
# 综合评测
# ============================================================================

def compute_python_metrics(
    code: str,
    test_id: int,
    expected_output_keywords: Optional[List[str]] = None,
    data_context: Optional[Dict[str, Any]] = None,
) -> PythonMetricsResult:
    """综合 Python 代码评测

    Args:
        code: Python 代码
        test_id: 用例 ID
        expected_output_keywords: 输出中应该包含的关键词
        data_context: 数据上下文

    Returns:
        PythonMetricsResult
    """
    result = PythonMetricsResult(test_id=test_id)

    # 1. 语法检查
    valid, err = check_python_syntax(code)
    result.syntax_valid = valid
    if not valid:
        result.error_message = err
        return result

    # 2. 安全检查
    safe, err = check_python_safety(code)
    if not safe:
        result.error_message = f"Safety check failed: {err}"
        return result

    # 3. 运行时执行
    success, stdout, stderr, elapsed = execute_python_code(
        code, data_context, timeout_sec=30
    )
    result.execution_success = success
    result.stdout = stdout
    result.stderr = stderr
    result.execution_time_ms = elapsed

    if not success:
        result.error_message = stderr or "Execution failed"
        return result

    # 4. 输出正确性检查
    if expected_output_keywords:
        output_text = (stdout + stderr).lower()
        result.output_has_result = all(
            kw.lower() in output_text for kw in expected_output_keywords
        )
        if not result.output_has_result:
            missing = [kw for kw in expected_output_keywords if kw.lower() not in output_text]
            result.error_message = f"Missing expected output keywords: {missing}"

    return result

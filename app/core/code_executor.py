"""
代码执行器服务 — Python 代码安全执行引擎

【在系统中的地位】
  当 LLM 生成了 Python 分析代码后，需要一个安全的执行环境来运行它。
  本服务提供三种执行模式，从本地 subprocess 到 Docker 沙箱隔离。

【模块连接】
  上游 (谁调用 CodeExecutor):
    - workflows/nodes/python_execute.py → 工作流中执行 LLM 生成的 Python 代码
      输入: sql_result (SQL 查询结果数据) + python_code (LLM 生成的代码)
      输出: ExecutionResult (success, output, error, charts, data)

  依赖:
    - core/llm.py:llm_service → AISimExecutor 用 LLM 模拟代码执行
    - core/config.py:settings.code_executor → 执行器类型和参数配置

  Java 对应:
    CodeExecutor ≈ CodePoolExecutorService.java
    LocalExecutor ≈ LocalCodeExecutor
    DockerExecutor ≈ DockerCodeExecutor
    AISimExecutor ≈ AISimulationExecutor

【三种执行模式】
  1. LocalExecutor (默认): subprocess.run(["python", code_file])
     - 优点: 简单、快速、无额外依赖
     - 缺点: 代码在宿主机运行，有安全风险
     - 适用: 开发环境、可信代码

  2. DockerExecutor: Docker 容器中执行
     - 优点: 完全隔离，安全
     - 缺点: 需要 Docker 环境，启动慢
     - 适用: 生产环境

  3. AISimExecutor: LLM 模拟执行结果
     - 优点: 不需要实际执行环境
     - 缺点: 结果不准确，可能产生幻觉
     - 适用: 快速原型、无 Python 环境时
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
import subprocess
import tempfile
import os
import json
import shutil
import logging
from .llm import llm_service
from .config import settings
from .text_utils import clean_code_block

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str
    error: Optional[str] = None
    charts: list[str] = None  # 生成的图表文件路径列表
    data: Optional[Any] = None  # 返回的数据

    def __post_init__(self):
        if self.charts is None:
            self.charts = []


class CodeExecutor(ABC):
    """代码执行器抽象基类"""

    @abstractmethod
    async def execute(self, code: str, data: Any = None) -> ExecutionResult:
        """
        执行代码

        Args:
            code: Python 代码
            data: 输入数据

        Returns:
            执行结果
        """
        pass


class LocalExecutor(CodeExecutor):
    """本地执行器"""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    async def execute(self, code: str, data: Any = None) -> ExecutionResult:
        """
        在本地执行 Python 代码

        Args:
            code: Python 代码
            data: 输入数据（会作为 sql_result 变量注入）

        Returns:
            执行结果
        """
        logger.info("[LocalExecutor] Executing Python code")

        try:
            # 创建临时目录
            with tempfile.TemporaryDirectory() as tmpdir:
                # 准备代码文件
                code_file = os.path.join(tmpdir, "script.py")
                data_file = os.path.join(tmpdir, "data.json")

                # 注入数据
                if data:
                    with open(data_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)

                    # 在代码前添加数据加载
                    # 使用 !r (repr) 确保 Windows 路径中的反斜杠被正确转义
                    # 避免 \U, \u 等被解释为 unicode 转义序列
                    code = f"""
import json
with open({data_file!r}, 'r', encoding='utf-8') as f:
    sql_result = json.load(f)

{code}
"""

                # 写入代码
                with open(code_file, "w", encoding="utf-8") as f:
                    f.write(code)

                # 执行代码
                result = subprocess.run(
                    ["python", code_file],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout
                )

                # 收集生成的图表
                charts = []
                for file in os.listdir(tmpdir):
                    if file.endswith((".png", ".jpg", ".jpeg", ".svg")):
                        chart_path = os.path.join(tmpdir, file)
                        # TODO: 将图表复制到持久化目录
                        charts.append(file)

                if result.returncode == 0:
                    logger.info("[LocalExecutor] Execution successful")
                    return ExecutionResult(
                        success=True,
                        output=result.stdout,
                        charts=charts
                    )
                else:
                    logger.error(f"[LocalExecutor] Execution failed: {result.stderr}")
                    return ExecutionResult(
                        success=False,
                        output=result.stdout,
                        error=result.stderr
                    )

        except subprocess.TimeoutExpired:
            logger.error(f"[LocalExecutor] Execution timeout after {self.timeout}s")
            return ExecutionResult(
                success=False,
                output="",
                error=f"执行超时（{self.timeout}秒）"
            )
        except Exception as e:
            logger.error(f"[LocalExecutor] Execution error: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=str(e)
            )


class AISimExecutor(CodeExecutor):
    """AI 模拟执行器（不实际执行代码）"""

    async def execute(self, code: str, data: Any = None) -> ExecutionResult:
        """
        使用 LLM 模拟代码执行结果

        Args:
            code: Python 代码
            data: 输入数据

        Returns:
            模拟的执行结果
        """
        logger.info("[AISimExecutor] Simulating Python execution with LLM")

        try:
            prompt = f"""你是一个 Python 代码执行模拟器。
给定以下 Python 代码和输入数据，模拟执行结果。

输入数据:
{json.dumps(data, ensure_ascii=False, indent=2) if data else "无"}

Python 代码:
```python
{code}
```

请模拟执行这段代码，返回：
1. 标准输出（print 的内容）
2. 是否会生成图表（如果有 plt.savefig）
3. 主要的分析结论

以 JSON 格式返回：
{{
  "output": "模拟的标准输出",
  "charts": ["chart1.png"],
  "analysis": "分析结论"
}}
"""

            result_text = await llm_service.chat("", prompt, temperature=0.0)
            result_text = clean_code_block(result_text, lang="json")

            # 解析结果
            result_json = json.loads(result_text)

            logger.info("[AISimExecutor] Simulation successful")
            return ExecutionResult(
                success=True,
                output=result_json.get("output", ""),
                charts=result_json.get("charts", []),
                data=result_json.get("analysis")
            )

        except Exception as e:
            logger.error(f"[AISimExecutor] Simulation error: {e}")
            return ExecutionResult(
                success=False,
                output="",
                error=f"模拟执行失败: {str(e)}"
            )


class DockerExecutor(CodeExecutor):
    """Docker 容器执行器 — 安全隔离的 Python 代码执行

    使用 docker run 在独立容器中执行代码:
      - 内存限制: 从 settings.code_executor.limit_memory 读取（默认 512M）
      - CPU 限制: 单核 (--cpus=1)
      - 网络隔离: 禁用网络 (--network none)
      - 只读根文件系统: --read-only，仅 temp 目录可写
      - 超时控制: 从 settings.code_executor.code_timeout 读取（默认 60s）
      - 非 root 用户: --user 1000:1000
      - 禁止特权模式: --security-opt=no-new-privileges

    Docker 镜像: python:3.11-slim（不含 pandas/matplotlib）
    如需数据分析包，在 data/requirements.txt 中列出，
    或使用 continuumio/anaconda3:latest
    """

    DOCKER_IMAGE = "python:3.11-slim"

    def __init__(self, timeout: int = 60, memory: str = "512M"):
        self.timeout = timeout
        self.memory = memory

    async def execute(self, code: str, data: Any = None) -> ExecutionResult:
        logger.info("[DockerExecutor] Executing Python code in Docker container")

        # 检查 Docker 是否可用
        if not shutil.which("docker"):
            return ExecutionResult(
                success=False,
                output="",
                error="Docker 未安装或不在 PATH 中，无法使用 Docker 执行器",
            )

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                code_file = os.path.join(tmpdir, "script.py")
                data_file = os.path.join(tmpdir, "data.json")

                # 写入数据文件
                if data:
                    with open(data_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)

                    code = f"""
import json
with open('/tmp/data.json', 'r', encoding='utf-8') as f:
    sql_result = json.load(f)

{code}
"""

                # 写入代码文件
                with open(code_file, "w", encoding="utf-8") as f:
                    f.write(code)

                # 构建 docker run 命令
                cmd = [
                    "docker", "run",
                    "--rm",                          # 执行完自动删除容器
                    "--cpus=1",                      # 限制 CPU 单核
                    f"--memory={self.memory}",        # 内存限制
                    "--network", "none",             # 禁用网络
                    "--read-only",                   # 只读根文件系统
                    "--tmpfs", "/tmp:exec",           # /tmp 可读写执行
                    "--security-opt=no-new-privileges",  # 禁止提权
                    "--user", "1000:1000",            # 非 root
                    "-v", f"{tmpdir}:/tmp:ro",       # 只读挂载代码目录
                    self.DOCKER_IMAGE,
                    "python", "/tmp/script.py",
                ]

                logger.debug("[DockerExecutor] Running: %s", " ".join(cmd))

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                )

                # 收集图表（Docker 无法直接输出文件到宿主机，改为检查 stdout）
                charts = []
                stderr = result.stderr or ""

                if result.returncode == 0:
                    logger.info("[DockerExecutor] Execution successful")
                    return ExecutionResult(
                        success=True,
                        output=result.stdout,
                        error=stderr if stderr else None,
                        charts=charts,
                    )
                else:
                    # Docker 退出码 137 = SIGKILL (OOM)，124 = timeout
                    if result.returncode == 137:
                        err = f"容器内存超限 (OOM)，限制: {self.memory}"
                    elif result.returncode == 124:
                        err = f"执行超时 ({self.timeout}s)"
                    else:
                        err = stderr or result.stdout or f"Exit code: {result.returncode}"
                    logger.error(f"[DockerExecutor] Execution failed (exit={result.returncode}): {err[:200]}")
                    return ExecutionResult(
                        success=False,
                        output=result.stdout,
                        error=err,
                    )

        except subprocess.TimeoutExpired:
            logger.error(f"[DockerExecutor] Timeout after {self.timeout}s")
            return ExecutionResult(
                success=False,
                output="",
                error=f"Docker 执行超时（{self.timeout}秒）",
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                output="",
                error="Docker 命令不可用，请确认 Docker 已安装并在 PATH 中",
            )
        except Exception as e:
            logger.exception("[DockerExecutor] Unexpected error")
            return ExecutionResult(
                success=False,
                output="",
                error=f"Docker 执行器错误: {str(e)}",
            )


# 执行器工厂
class ExecutorFactory:
    """执行器工厂"""

    @staticmethod
    def create(executor_type: str = "local") -> CodeExecutor:
        """
        创建执行器

        Args:
            executor_type: 执行器类型 (local/docker/ai-sim)

        Returns:
            执行器实例
        """
        if executor_type == "local":
            return LocalExecutor(timeout=settings.code_executor.code_timeout)
        elif executor_type == "docker":
            return DockerExecutor(
                timeout=settings.code_executor.code_timeout,
                memory=settings.code_executor.limit_memory,
            )
        elif executor_type == "ai-sim":
            return AISimExecutor()
        else:
            raise ValueError(f"Unknown executor type: {executor_type}")


# 全局执行器实例
_executor: Optional[CodeExecutor] = None


def get_code_executor(executor_type: str = "local") -> CodeExecutor:
    """获取代码执行器"""
    global _executor
    if _executor is None:
        _executor = ExecutorFactory.create(executor_type)
    return _executor

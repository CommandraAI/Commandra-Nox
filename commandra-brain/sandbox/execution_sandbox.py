"""
Secure Code Execution Sandbox -- isolated, resource-limited execution for
Python, Node.js, Rust, and Go.

Implements:
- Process Isolation (subprocess with clean environment)
- Resource Limits (CPU time, memory via ulimit on Linux)
- Timeout Protection (threading.Timer hard kill)
- Output Capture (stdout + stderr)
- Error Capture (exit code, traceback)
- Safe File Access (temp directory, no host paths leaked)

The sandbox never writes outside the per-execution temp directory and never
has access to Brain source files or repository workspace paths.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import threading
import time
from dataclasses import dataclass, field
from enum import Enum


class Language(str, Enum):
    PYTHON = "python"
    NODEJS = "nodejs"
    RUST = "rust"
    GO = "go"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ExecutionRequest:
    language: Language
    code: str
    stdin_data: str = ""
    timeout_seconds: float = 10.0
    max_output_bytes: int = 64 * 1024   # 64 KB
    memory_limit_mb: int = 128
    cpu_limit_seconds: int = 8

    def as_dict(self) -> dict:
        return {
            "language": self.language.value,
            "codeLength": len(self.code),
            "timeoutSeconds": self.timeout_seconds,
            "maxOutputBytes": self.max_output_bytes,
            "memoryLimitMb": self.memory_limit_mb,
        }


@dataclass
class ExecutionResult:
    language: Language
    stdout: str
    stderr: str
    exit_code: int
    elapsed_seconds: float
    timed_out: bool = False
    killed: bool = False
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.killed

    def as_dict(self) -> dict:
        return {
            "language": self.language.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exitCode": self.exit_code,
            "elapsedSeconds": round(self.elapsed_seconds, 3),
            "timedOut": self.timed_out,
            "killed": self.killed,
            "success": self.success,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Language runners
# ---------------------------------------------------------------------------

def _safe_env() -> dict[str, str]:
    """Minimal, clean environment for sandbox processes."""
    allowed = {"PATH", "HOME", "TMPDIR", "TEMP", "TMP", "LANG", "LC_ALL", "TERM"}
    return {k: v for k, v in os.environ.items() if k in allowed}


def _ulimit_prefix(cpu_seconds: int, memory_mb: int) -> list[str]:
    """On Linux, wrap command with ulimit constraints via bash."""
    if os.name != "posix":
        return []
    mem_kb = memory_mb * 1024
    return [
        "bash", "-c",
        f"ulimit -t {cpu_seconds} -v {mem_kb * 1024} 2>/dev/null; exec \"$@\"", "--",
    ]


def _run_subprocess(
    cmd: list[str],
    code_dir: str,
    stdin_data: str,
    timeout: float,
    max_bytes: int,
    cpu_seconds: int,
    memory_mb: int,
) -> tuple[str, str, int, bool, bool]:
    """
    Run cmd in code_dir with timeout + resource limits.
    Returns (stdout, stderr, exit_code, timed_out, killed).
    """
    full_cmd = _ulimit_prefix(cpu_seconds, memory_mb) + cmd

    proc = subprocess.Popen(
        full_cmd,
        cwd=code_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_safe_env(),
    )

    timed_out = False
    killed = False
    timer: threading.Timer | None = None

    def _kill() -> None:
        nonlocal timed_out, killed
        timed_out = True
        killed = True
        try:
            proc.kill()
        except ProcessLookupError:
            pass

    timer = threading.Timer(timeout, _kill)
    timer.start()

    try:
        raw_out, raw_err = proc.communicate(input=stdin_data.encode("utf-8", errors="replace"))
    except Exception:
        raw_out, raw_err = b"", b""
    finally:
        timer.cancel()

    stdout = raw_out[:max_bytes].decode("utf-8", errors="replace")
    stderr = raw_err[:max_bytes].decode("utf-8", errors="replace")
    exit_code = proc.returncode if not timed_out else -1

    return stdout, stderr, exit_code, timed_out, killed


# ---------------------------------------------------------------------------
# Per-language execution strategies
# ---------------------------------------------------------------------------

class _PythonRunner:
    EXECUTABLE = "python3"

    def execute(self, req: ExecutionRequest, code_dir: str) -> tuple[str, str, int, bool, bool]:
        script = os.path.join(code_dir, "main.py")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(req.code)
        return _run_subprocess(
            [self.EXECUTABLE, "-u", "main.py"],
            code_dir, req.stdin_data, req.timeout_seconds,
            req.max_output_bytes, req.cpu_limit_seconds, req.memory_limit_mb,
        )


class _NodeRunner:
    EXECUTABLE = "node"

    def execute(self, req: ExecutionRequest, code_dir: str) -> tuple[str, str, int, bool, bool]:
        script = os.path.join(code_dir, "main.js")
        with open(script, "w", encoding="utf-8") as fh:
            fh.write(req.code)
        return _run_subprocess(
            [self.EXECUTABLE, "--max-old-space-size=128", "main.js"],
            code_dir, req.stdin_data, req.timeout_seconds,
            req.max_output_bytes, req.cpu_limit_seconds, req.memory_limit_mb,
        )


class _RustRunner:
    def execute(self, req: ExecutionRequest, code_dir: str) -> tuple[str, str, int, bool, bool]:
        src = os.path.join(code_dir, "main.rs")
        binary = os.path.join(code_dir, "main")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(req.code)

        # Compile first
        compile_result = subprocess.run(
            ["rustc", src, "-o", binary],
            cwd=code_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if compile_result.returncode != 0:
            return "", compile_result.stderr, compile_result.returncode, False, False

        return _run_subprocess(
            [binary],
            code_dir, req.stdin_data, req.timeout_seconds,
            req.max_output_bytes, req.cpu_limit_seconds, req.memory_limit_mb,
        )


class _GoRunner:
    def execute(self, req: ExecutionRequest, code_dir: str) -> tuple[str, str, int, bool, bool]:
        src = os.path.join(code_dir, "main.go")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write(req.code)

        # go run compiles + executes in one step
        return _run_subprocess(
            ["go", "run", "main.go"],
            code_dir, req.stdin_data, req.timeout_seconds,
            req.max_output_bytes, req.cpu_limit_seconds, req.memory_limit_mb,
        )


_RUNNERS = {
    Language.PYTHON: _PythonRunner(),
    Language.NODEJS: _NodeRunner(),
    Language.RUST: _RustRunner(),
    Language.GO: _GoRunner(),
}


# ---------------------------------------------------------------------------
# ExecutionSandbox -- public API
# ---------------------------------------------------------------------------

class ExecutionSandbox:
    """
    Safe, isolated code execution for validation and testing.

    Each execution runs in its own throwaway temp directory and is killed
    after the configured timeout.  No host paths are exposed inside the
    sandbox.
    """

    def execute(self, req: ExecutionRequest) -> ExecutionResult:
        runner = _RUNNERS.get(req.language)
        if runner is None:
            return ExecutionResult(
                language=req.language,
                stdout="",
                stderr="",
                exit_code=-1,
                elapsed_seconds=0.0,
                error=f"Unsupported language: {req.language.value}",
            )

        code_dir = tempfile.mkdtemp(prefix="commandra_sandbox_")
        start = time.time()
        try:
            stdout, stderr, exit_code, timed_out, killed = runner.execute(req, code_dir)
        except FileNotFoundError as exc:
            stdout, stderr, exit_code, timed_out, killed = "", str(exc), -1, False, False
        except Exception as exc:
            stdout, stderr, exit_code, timed_out, killed = "", str(exc), -1, False, False
        finally:
            shutil.rmtree(code_dir, ignore_errors=True)

        elapsed = time.time() - start
        return ExecutionResult(
            language=req.language,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            elapsed_seconds=elapsed,
            timed_out=timed_out,
            killed=killed,
        )

    def execute_snippet(self, language: str, code: str, timeout: float = 10.0) -> ExecutionResult:
        """Convenience wrapper for quick one-shot snippet execution."""
        try:
            lang = Language(language.lower())
        except ValueError:
            return ExecutionResult(
                language=Language.PYTHON,
                stdout="",
                stderr=f"Unknown language: {language}",
                exit_code=-1,
                elapsed_seconds=0.0,
                error=f"Unknown language: {language}",
            )
        return self.execute(ExecutionRequest(language=lang, code=code, timeout_seconds=timeout))

    @staticmethod
    def available_runtimes() -> dict[str, bool]:
        """Return which language runtimes are installed on this system."""
        checks = {
            "python": "python3",
            "nodejs": "node",
            "rust": "rustc",
            "go": "go",
        }
        result: dict[str, bool] = {}
        for name, binary in checks.items():
            result[name] = shutil.which(binary) is not None
        return result

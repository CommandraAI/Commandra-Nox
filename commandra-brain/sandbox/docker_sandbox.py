"""
Docker Sandbox -- execute generated code inside isolated Docker containers.

Uses docker-py (pip install docker) for container lifecycle management.
Falls back gracefully when Docker is not installed or the daemon is not running.

The Docker sandbox provides stronger isolation than the subprocess sandbox:
- Separate filesystem namespace
- Network isolation (no external network by default)
- CPU and memory limits enforced by the container runtime
- Automatic container cleanup after execution
"""
from __future__ import annotations
import base64
import shutil
import time
from dataclasses import dataclass

_DOCKER_AVAILABLE = False
try:
    import docker  # type: ignore
    _DOCKER_AVAILABLE = True
except ImportError:
    pass

# Default images per language -- all are official Docker Hub images
_IMAGES: dict[str, str] = {
    "python":  "python:3.12-slim",
    "nodejs":  "node:20-slim",
    "rust":    "rust:1.80-slim",
    "go":      "golang:1.23-alpine",
    "bash":    "alpine:latest",
    "ruby":    "ruby:3.3-slim",
    "java":    "eclipse-temurin:21-jre-alpine",
}

_ENTRYPOINTS: dict[str, list[str]] = {
    "python":  ["python3", "-u", "-c"],
    "nodejs":  ["node", "-e"],
    "bash":    ["sh", "-c"],
    "ruby":    ["ruby", "-e"],
}

_FILE_RUNNERS: dict[str, tuple[str, str]] = {
    # (filename, run_command_template)
    "rust": ("main.rs",  "rustc main.rs -o main 2>&1 && ./main"),
    "go":   ("main.go",  "go run main.go"),
    "java": ("Main.java","javac Main.java 2>&1 && java Main"),
}


@dataclass
class DockerExecutionResult:
    language: str
    stdout: str
    stderr: str
    exit_code: int
    elapsed_seconds: float
    image: str
    timed_out: bool = False
    available: bool = True
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def as_dict(self) -> dict:
        return {
            "language": self.language,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exitCode": self.exit_code,
            "elapsedSeconds": round(self.elapsed_seconds, 3),
            "image": self.image,
            "timedOut": self.timed_out,
            "available": self.available,
            "success": self.success,
            "error": self.error,
        }


class DockerSandbox:
    """
    Isolated code execution inside Docker containers.

    Each call creates a fresh container, runs the code, captures output,
    and removes the container — no state persists between executions.
    """

    def __init__(self) -> None:
        self._client = None
        if _DOCKER_AVAILABLE:
            try:
                self._client = docker.from_env(timeout=10)
                self._client.ping()
            except Exception:
                self._client = None

    def available(self) -> bool:
        return _DOCKER_AVAILABLE and self._client is not None

    def available_images(self) -> dict[str, str]:
        return dict(_IMAGES)

    def execute(
        self,
        language: str,
        code: str,
        timeout_seconds: float = 15.0,
        memory_mb: int = 256,
        cpu_quota: int = 50000,      # 50% of one CPU (cgroups v2)
        network_disabled: bool = True,
    ) -> DockerExecutionResult:
        if not self.available():
            return DockerExecutionResult(
                language=language, stdout="", stderr="", exit_code=-1,
                elapsed_seconds=0.0, image="", available=False,
                error="Docker not available. Install docker-py: pip install docker; "
                      "and ensure the Docker daemon is running."
            )

        image = _IMAGES.get(language.lower())
        if not image:
            return DockerExecutionResult(
                language=language, stdout="", stderr="", exit_code=-1,
                elapsed_seconds=0.0, image="",
                error=f"No Docker image configured for language '{language}'. "
                      f"Supported: {', '.join(_IMAGES.keys())}"
            )

        # Build the command
        if language.lower() in _ENTRYPOINTS:
            cmd = _ENTRYPOINTS[language.lower()] + [code]
            volumes = {}
        elif language.lower() in _FILE_RUNNERS:
            filename, run_cmd = _FILE_RUNNERS[language.lower()]
            encoded = base64.b64encode(code.encode()).decode()
            # Write file then run — use sh to handle compilation
            cmd = ["sh", "-c", f"echo '{encoded}' | base64 -d > {filename} && {run_cmd}"]
            volumes = {}
        else:
            cmd = ["sh", "-c", code]
            volumes = {}

        start = time.time()
        container = None
        try:
            container = self._client.containers.run(
                image=image,
                command=cmd,
                detach=True,
                network_disabled=network_disabled,
                mem_limit=f"{memory_mb}m",
                cpu_quota=cpu_quota,
                read_only=False,
                remove=False,
                stdout=True,
                stderr=True,
            )
            timed_out = False
            try:
                exit_code = container.wait(timeout=timeout_seconds)["StatusCode"]
            except Exception:
                timed_out = True
                container.kill()
                exit_code = -1

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")[:32768]
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")[:8192]
            elapsed = time.time() - start

            return DockerExecutionResult(
                language=language, stdout=stdout, stderr=stderr,
                exit_code=exit_code, elapsed_seconds=elapsed,
                image=image, timed_out=timed_out,
            )
        except Exception as exc:
            return DockerExecutionResult(
                language=language, stdout="", stderr="", exit_code=-1,
                elapsed_seconds=time.time() - start, image=image, error=str(exc),
            )
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    def pull_image(self, language: str) -> dict:
        """Pre-pull a language image so first execution is fast."""
        if not self.available():
            return {"pulled": False, "error": "Docker not available"}
        image = _IMAGES.get(language.lower())
        if not image:
            return {"pulled": False, "error": f"Unknown language: {language}"}
        try:
            self._client.images.pull(image)
            return {"pulled": True, "image": image}
        except Exception as exc:
            return {"pulled": False, "image": image, "error": str(exc)}

    def list_pulled_images(self) -> list[str]:
        if not self.available():
            return []
        try:
            pulled = {img.tags[0] for img in self._client.images.list() if img.tags}
            return [lang for lang, img in _IMAGES.items() if img in pulled]
        except Exception:
            return []

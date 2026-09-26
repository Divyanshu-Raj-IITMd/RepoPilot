"""Execution sandboxes for running generated tests / user code safely.

Two implementations:
  * DockerSandboxExecutor — the recommended one for local use. Runs commands in
    an ephemeral `python:3.11-slim` container with:
      --network none        (no network access)
      --read-only rootfs    (only an overlay workspace is writable)
      --memory / --cpus     (resource caps)
      a stripped environment (no secrets, no env vars from the host)
  * SubprocessSandboxExecutor — dependency-free fallback (used in CI and where
    Docker is unavailable). Copies the repo into a temp workspace, strips the
    environment to a whitelist, and applies rlimits (CPU, address space,
    nofile, nproc) + a hard timeout. Weaker isolation than Docker — the API
    always reports which executor was used. On Windows (no `resource` module)
    the rlimit caps are skipped and isolation is env-whitelist + timeout.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass

from app.config import Settings

try:  # POSIX-only module. On Windows the subprocess sandbox degrades to
    import resource  # env-whitelist + hard timeout (no rlimit caps).
except ImportError:  # pragma: no cover (Windows)
    resource = None  # type: ignore[assignment]

ENV_WHITELIST = ("PATH", "HOME", "LANG", "LC_ALL", "PYTHONIOENCODING",
                 "PYTHONDONTWRITEBYTECODE", "SYSTEMROOT", "SYSTEMDRIVE",
                 "TEMP", "TMP", "TMPDIR", "USERPROFILE")


@dataclass
class ExecResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    duration_s: float
    executor: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict:
        return {
            "command": self.command, "exit_code": self.exit_code,
            "stdout": self.stdout[-8000:], "stderr": self.stderr[-8000:],
            "timed_out": self.timed_out, "duration_s": round(self.duration_s, 2),
            "executor": self.executor,
        }


class BaseExecutor:
    name = "base"

    def run(self, command: list[str], workspace: str, timeout: int = 60) -> ExecResult:
        raise NotImplementedError

    def make_workspace(self, repo_root: str) -> str:
        """Copy the repo into a scratch dir so we never touch the original."""
        ws = tempfile.mkdtemp(prefix="repopilot-ws-")
        for item in os.listdir(repo_root):
            if item in (".git", ".venv", "venv", "node_modules", "__pycache__"):
                continue
            src = os.path.join(repo_root, item)
            dst = os.path.join(ws, item)
            try:
                shutil.copytree(src, dst) if os.path.isdir(src) else shutil.copy2(src, dst)
            except OSError:
                pass
        return ws


def _limits():  # pragma: no cover - runs inside the child process
    if resource is None:  # Windows: preexec_fn is not used there at all
        return
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
        resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    except Exception:
        pass


class SubprocessExecutor(BaseExecutor):
    """Hardened local subprocess: env whitelist, rlimits, timeout, scratch workspace."""

    name = "subprocess"

    def run(self, command: list[str], workspace: str, timeout: int = 60) -> ExecResult:
        env = {k: os.environ[k] for k in ENV_WHITELIST if k in os.environ}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        # force UTF-8 in the child so file writes / stdout are identical on
        # every platform (Windows children would otherwise default to cp1252)
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # preexec_fn is unsupported on Windows (and unneeded when there are no
        # rlimits to apply) — only pass it when the POSIX resource module exists
        preexec = _limits if resource is not None else None
        t0 = time.time()
        try:
            proc = subprocess.run(
                command, cwd=workspace, env=env, timeout=timeout,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", preexec_fn=preexec,
            )
            return ExecResult(command=command, exit_code=proc.returncode,
                              stdout=proc.stdout, stderr=proc.stderr, timed_out=False,
                              duration_s=time.time() - t0, executor=self.name)
        except subprocess.TimeoutExpired as exc:
            return ExecResult(command=command, exit_code=-1,
                              stdout=(exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                              stderr=f"execution timed out after {timeout}s",
                              timed_out=True, duration_s=time.time() - t0, executor=self.name)


class DockerExecutor(BaseExecutor):
    """Ephemeral, network-disabled, read-only containers with a writable overlay."""

    name = "docker"
    IMAGE = "python:3.11-slim"

    def __init__(self) -> None:
        if not shutil.which("docker"):
            raise RuntimeError("docker binary not found")
        # the binary existing is not enough (e.g. Docker Desktop installed but
        # not running) — probe the daemon before selecting this executor
        try:
            probe = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                capture_output=True, text=True, timeout=10)
        except (subprocess.TimeoutExpired, OSError) as exc:
            raise RuntimeError(f"docker daemon not reachable: {exc}") from exc
        if probe.returncode != 0:
            raise RuntimeError("docker daemon not reachable (is Docker running?)")

    def run(self, command: list[str], workspace: str, timeout: int = 60) -> ExecResult:
        docker_cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=64m",
            "--memory", "512m", "--cpus", "1",
            "--pids-limit", "64",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "-v", f"{os.path.abspath(workspace)}:/workspace:rw",
            "-w", "/workspace",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONUTF8=1",
            self.IMAGE,
            *command,
        ]
        t0 = time.time()
        try:
            proc = subprocess.run(docker_cmd, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace",
                                  timeout=timeout + 30)
            return ExecResult(command=command, exit_code=proc.returncode,
                              stdout=proc.stdout, stderr=proc.stderr, timed_out=False,
                              duration_s=time.time() - t0, executor=self.name)
        except subprocess.TimeoutExpired:
            return ExecResult(command=command, exit_code=-1, stdout="",
                              stderr=f"docker execution timed out after {timeout + 30}s",
                              timed_out=True, duration_s=time.time() - t0, executor=self.name)


def get_executor(settings: Settings | None = None) -> BaseExecutor:
    settings = settings or get_settings_safe()
    mode = settings.executor
    if mode in ("docker", "auto"):
        try:
            return DockerExecutor()
        except Exception:
            if mode == "docker":
                raise
    return SubprocessExecutor()


def get_settings_safe():
    from app.config import get_settings
    return get_settings()


PYTEST_BIN = [sys.executable, "-m", "pytest"]


def pytest_command(test_path: str) -> list[str]:
    return [*PYTEST_BIN, test_path, "-q", "--tb=short", "-p", "no:cacheprovider",
            "--no-header", "--color=no"]

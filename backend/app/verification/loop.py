"""The verification loop — RepoPilot's core differentiator.

    generate  ->  static checks  ->  run tests (sandboxed)  ->  analyze
      ^                                                          |
      └------------------ propose correction -------------------┯
                                                                 v
                                             verdict: validated | rejected

An AI-generated recommendation is only *reported* once it passes, and every
verdict carries the actual pass counts, logs and iterations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.sandbox.executor import BaseExecutor, pytest_command


@dataclass
class TestCase:
    label: str
    category: str          # normal | empty | zero | negative | large | boundary | invalid
    call_src: str          # python expression calling the target
    expectation: str       # no_crash | ge_zero | raises | exact
    expected_value: str = ""


@dataclass
class TestRun:
    passed: int
    failed: int
    errors: int
    failed_tests: list[str] = field(default_factory=list)
    output: str = ""
    timed_out: bool = False
    exit_code: int = -1
    duration_s: float = 0.0
    executor: str = ""

    def to_dict(self) -> dict:
        return {"passed": self.passed, "failed": self.failed, "errors": self.errors,
                "failed_tests": self.failed_tests, "output": self.output[-4000:],
                "timed_out": self.timed_out, "exit_code": self.exit_code,
                "duration_s": round(self.duration_s, 2), "executor": self.executor}


@dataclass
class VerificationResult:
    status: str                    # validated | validated_after_fix | rejected | error
    target: str
    total: int
    passed: int
    iterations: list[dict] = field(default_factory=list)
    patch: dict | None = None   # suggested source fix (file, line, code)
    summary: str = ""
    test_file: str = ""
    test_code: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status, "target": self.target, "total": self.total,
            "passed": self.passed, "iterations": self.iterations,
            "patch": self.patch, "summary": self.summary,
            "test_file": self.test_file, "test_code": self.test_code,
        }


# ------------------------------------------------------------------ pytest I/O

def run_pytest(executor: BaseExecutor, workspace: str, test_path: str,
               timeout: int) -> TestRun:
    cmd = pytest_command(test_path)
    res = executor.run(cmd, workspace, timeout=timeout)
    return parse_pytest_output(res)


def parse_pytest_output(res) -> TestRun:
    out = (res.stdout or "") + "\n" + (res.stderr or "")
    summary = re.search(r"(\d+) passed", out)
    failed = re.search(r"(\d+) failed", out)
    errors = re.search(r"(\d+) error", out)
    failed_tests = re.findall(r"^FAILED\s+(\S+?)(?:\s+-\s+.*)?$", out, re.M)
    error_tests = re.findall(r"^ERROR\s+(\S+?)(?:\s+-\s+.*)?$", out, re.M)
    return TestRun(
        passed=int(summary.group(1)) if summary else 0,
        failed=int(failed.group(1)) if failed else 0,
        errors=int(errors.group(1)) if errors else 0,
        failed_tests=failed_tests + error_tests,
        output=out[-4000:], timed_out=res.timed_out, exit_code=res.exit_code,
        duration_s=res.duration_s, executor=res.executor,
    )


# ------------------------------------------------------- failure classification

def classify_failures(run: TestRun) -> dict[str, list[str]]:
    """Map failed test ids to failure classes based on pytest -v --tb=line output."""
    classes: dict[str, list[str]] = {
        "missing_validation": [], "value_bug": [], "crash": [], "assertion": [],
    }
    for t in run.failed_tests:
        label = t.rsplit("::", 1)[-1]
        block = _block_for(run.output, t)
        if "::" not in t:
            classes["crash"].append(label)  # collection error (whole file)
        elif "DID NOT RAISE" in block:
            classes["missing_validation"].append(label)
        elif re.search(r"AssertionError", block) and ("ge_zero" in label or "normal" in label):
            classes["value_bug"].append(label)
        elif re.search(r"AssertionError", block):
            classes["assertion"].append(label)
        elif re.search(r"(TypeError|KeyError|IndexError|AttributeError|ZeroDivisionError|"
                       r"ValueError|NameError)", block):
            classes["crash"].append(label)
        else:
            classes["assertion"].append(label)
    return classes


def _block_for(output: str, test_id: str) -> str:
    label = test_id.rsplit("::", 1)[-1]
    # 1) short-summary line that carries the exception detail ("- Failed: ...")
    idx = output.find(test_id)
    if idx >= 0 and " - " in output[idx: idx + 250]:
        return output[idx: idx + 800]
    # 2) --tb=short failure section, headed by ____ label ____
    m = re.search(rf"_{{5,}}+\s*{re.escape(label)}\s*_{{5,}}", output)
    if m:
        return output[m.start(): m.start() + 900]
    # 3) any occurrence of the label, else the output tail
    idx = output.find(label)
    if idx >= 0:
        return output[max(0, idx - 50): idx + 700]
    return output[-1500:]

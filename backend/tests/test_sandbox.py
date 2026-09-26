"""Sandbox: subprocess executor env stripping, timeouts, pytest parsing."""


def test_env_is_stripped():
    import os

    from app.sandbox.executor import PYTEST_BIN, SubprocessExecutor
    os.environ["FAKE_SECRET"] = "leak-me"
    ex = SubprocessExecutor()
    import tempfile
    ws = tempfile.mkdtemp()
    open(f"{ws}/t.py", "w").write(
        "import os\nprint('SECRET_PRESENT' if 'FAKE_SECRET' in os.environ else 'CLEAN')\n")
    ex.run([*PYTEST_BIN, "-q", "--no-header", "-p", "no:cacheprovider", "t.py"],
                 ws, timeout=60)
    # run as a plain script instead to inspect the env
    script = ex.run([__import__("sys").executable, "t.py"], ws, timeout=60)
    assert "CLEAN" in script.stdout
    assert "SECRET_PRESENT" not in script.stdout


def test_timeout_enforced():
    import sys
    import tempfile

    from app.sandbox.executor import SubprocessExecutor
    ex = SubprocessExecutor()
    ws = tempfile.mkdtemp()
    open(f"{ws}/slow.py", "w").write("import time; time.sleep(30)\n")
    res = ex.run([sys.executable, "slow.py"], ws, timeout=2)
    assert res.timed_out is True


def test_parse_pytest_output():
    from app.verification.loop import parse_pytest_output

    class R:
        stdout = ("..F.\n____ test_bad ____\nt.py:5: in test_bad\n"
                  "E   Failed: DID NOT RAISE any of (ValueError,)\n"
                  "FAILED t.py::test_bad - Failed: DID NOT RAISE\n"
                  "1 failed, 3 passed in 0.01s\n")
        stderr = ""
        timed_out = False
        exit_code = 1
        duration_s = 0.01
        executor = "subprocess"
        command = []

    run = parse_pytest_output(R())
    assert run.passed == 3 and run.failed == 1
    assert run.failed_tests == ["t.py::test_bad"]


def test_executor_without_resource(monkeypatch, tmp_path):
    """Windows code path: no `resource` module -> no preexec_fn, still executes."""
    import sys

    from app.sandbox import executor as ex_mod

    monkeypatch.setattr(ex_mod, "resource", None, raising=False)
    ex = ex_mod.SubprocessExecutor()
    (tmp_path / "t.py").write_text(
        "import os\nprint('OK', 'FAKE_SECRET' not in os.environ)\n")
    res = ex.run([sys.executable, "t.py"], str(tmp_path), timeout=60)
    assert res.exit_code == 0
    assert "OK True" in res.stdout

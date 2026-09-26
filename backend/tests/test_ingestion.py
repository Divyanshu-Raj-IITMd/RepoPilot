"""Ingestion + parsing: walker, detectors, AST parser, secret scanner."""



def test_walker_indexes_demo_repo(demo_repo):
    files = demo_repo.graph.files
    assert "app/main.py" in files
    assert ".env" in files                      # dotfiles are indexed
    assert "app/services/users.py" in files
    assert all(".git" not in p for p in files)


def test_framework_and_database_detection(demo_repo):
    s = demo_repo.summary
    assert "FastAPI" in s.frameworks
    assert "SQLite" in s.databases
    assert s.entry_points == ["app/main.py"]


def test_route_table_extraction(demo_repo):
    routes = {(r.method, r.path): r for r in demo_repo.graph.routes}
    assert ("GET", "/api/users/{username}") in routes
    assert ("POST", "/api/orders") in routes
    handler = routes[("GET", "/api/users/{username}")]
    assert handler.handler == "get_user"
    assert handler.file == "app/routes/users.py"


def test_python_parser_extracts_symbols_and_signatures(demo_repo):
    g = demo_repo.graph
    syms = {s.qualified: s for s in g.symbols}
    assert "calculate_invoice" in syms
    assert "items" in syms["calculate_invoice"].signature
    assert "encode_token" in syms
    assert sym_returns_none(syms, "get_user_by_username") is True


def sym_returns_none(syms, name):
    return syms[name].returns_none


def test_none_return_tracking(demo_repo):
    """get_user_by_username explicitly returns None — the investigator's key signal."""
    g = demo_repo.graph
    sym = g.find_symbol("get_user_by_username")[0]
    assert sym.returns_none is True


def test_secret_scanner_finds_env_and_hardcoded_secrets(demo_repo):
    kinds = {f.kind for f in demo_repo.security.findings}
    assert "aws_access_key" in kinds
    assert "db_url_password" in kinds
    assert "assigned_secret" in kinds
    files = {f.file for f in demo_repo.security.findings}
    assert ".env" in files
    assert "app/auth/jwt.py" in files


def test_redaction():
    from app.sandbox.secret_scanner import redact
    text = 'SECRET_KEY = "super-secret-value-123"'
    out = redact(text)
    assert "super-secret-value-123" not in out
    assert "***REDACTED***" in out


def test_stale_clone_dir_is_cleaned_and_failure_leaves_no_debris(tmp_path, monkeypatch):
    """Windows regression: retrying an ingestion after a failed clone.

    A failed `git clone` used to leave a partial directory behind, and the
    pre-clone cleanup used ignore_errors=True (a no-op on locked Windows
    folders) — so every retry died with 'destination path already exists'.
    """
    import pytest

    from app.ingestion import cloner

    class FakeProc:
        returncode = 128
        stderr = "fatal: repository not found"
        stdout = ""

    monkeypatch.setattr(cloner.subprocess, "run", lambda *a, **k: FakeProc())

    clones = tmp_path / "clones"
    stale = clones / "stale"
    (stale / "junk").mkdir(parents=True)
    (stale / "junk" / "f.txt").write_text("partial clone debris")

    with pytest.raises(cloner.IngestError, match="repository not found"):
        cloner._clone("https://example.com/stale.git", str(clones))

    assert not stale.exists(), "stale/debris directory must not survive"


def test_clone_timeout_leaves_no_debris(tmp_path, monkeypatch):
    import subprocess

    import pytest

    from app.ingestion import cloner

    def fake_run(*a, **k):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(cloner.subprocess, "run", fake_run)
    clones = tmp_path / "clones"
    with pytest.raises(cloner.IngestError, match="timed out"):
        cloner._clone("https://example.com/slow.git", str(clones))
    assert not (clones / "slow").exists()


def test_clones_are_serialized_and_noninteractive(tmp_path, monkeypatch):
    """Concurrent ingestion retries must race neither each other nor a
    hidden credential dialog (private repos hung the server-side clone)."""
    import threading
    import time

    from app.ingestion import cloner

    class FakeProc:
        returncode = 0
        stderr = ""
        stdout = ""

    intervals: list[tuple[float, float]] = []
    envs: list[dict] = []

    def fake_run(cmd, **kwargs):
        t0 = time.time()
        time.sleep(0.15)  # simulate a slow clone
        envs.append(kwargs.get("env") or {})
        intervals.append((t0, time.time()))
        return FakeProc()

    monkeypatch.setattr(cloner.subprocess, "run", fake_run)
    threads = [threading.Thread(
        target=lambda: cloner._clone("https://example.com/cb.git", str(tmp_path)))
        for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(intervals) == 2
    # serialized: the second clone starts only after the first one finished
    assert intervals[1][0] >= intervals[0][1] - 0.02
    # credential prompts disabled -> no invisible GCM dialog can hang a clone
    for env in envs:
        assert env.get("GIT_TERMINAL_PROMPT") == "0"
        assert env.get("GCM_INTERACTIVE") == "never"


def test_locked_stale_dir_does_not_block_ingestion(tmp_path, monkeypatch):
    """A locked leftover clone dir must NEVER block ingestion.

    Every clone now targets a fresh unique directory; stale dirs are cleaned
    best-effort only. (Previously a locked 'clones/ContextBird' made every
    retry fail with 'cannot remove leftover clone directory'.)
    """
    import os

    from app.ingestion import cloner

    clones = tmp_path / "clones"
    stale = clones / "cb"
    (stale / "junk").mkdir(parents=True)

    real_rmtree = cloner.shutil.rmtree

    def locked_rmtree(path, *a, **k):
        if str(path).endswith("cb"):  # the stale dir is permanently locked
            raise OSError("file in use by another process")
        return real_rmtree(path, *a, **k)

    monkeypatch.setattr(cloner.shutil, "rmtree", locked_rmtree)

    class FakeProc:
        returncode = 0
        stderr = ""
        stdout = ""

    def fake_run(cmd, **kwargs):
        os.makedirs(cmd[-1], exist_ok=True)  # real git clone creates the target
        return FakeProc()

    monkeypatch.setattr(cloner.subprocess, "run", fake_run)

    target = cloner._clone("https://example.com/cb.git", str(clones))
    assert os.path.isdir(target), "clone must succeed despite the locked stale dir"
    assert target != str(stale), "must have used a fresh unique directory"
    assert stale.exists(), "locked debris is skipped, not fatal"

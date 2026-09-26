"""Agents: supervisor routing, search, investigation, review, verification."""


def test_classify_routes_intents():
    from app.agents.supervisor import classify
    assert classify("What is the architecture of this repo?") == "analyst"
    assert classify("What framework does this project use?") == "analyst"
    assert classify("Where is JWT authentication implemented?") == "search"
    assert classify("Who calls get_user_by_username?") == "search"
    assert classify("Why might /api/users return HTTP 500?") == "investigate"
    assert classify("generate tests for calculate_invoice") == "testgen"
    assert classify("review this diff", has_diff=True) == "review"


def test_search_cites_jwt_files(demo_repo):
    from app.agents.code_search import search
    result = search(demo_repo, "Where is JWT authentication implemented?")
    files = [c.file for c in result.citations]
    assert "app/auth/jwt.py" in files
    assert "app/middleware/auth.py" in files
    # every citation is auditable
    for c in result.citations:
        assert c.file in demo_repo.graph.files
        assert c.start_line >= 1


def test_search_dependency_answer(demo_repo):
    from app.agents.code_search import search
    result = search(demo_repo, "Which files import app/services/users?")
    dep = result.extra.get("dependency_answer") or ""
    assert "app/routes/users.py" in dep
    assert "app/auth/service.py" in dep


def test_investigator_finds_seeded_none_bug(demo_repo):
    from app.agents.issue_investigator import investigate
    result = investigate(demo_repo, "Why might GET /api/users/{username} return HTTP 500?")
    assert "app/routes/users.py" in [c.file for c in result.citations]
    cats = [f.category for f in result.findings]
    assert "unhandled_none" in cats
    none_finding = next(f for f in result.findings if f.category == "unhandled_none")
    assert none_finding.severity == "HIGH"
    assert "user" in none_finding.title


def test_investigator_surfaces_secrets_for_security_questions(demo_repo):
    from app.agents.issue_investigator import investigate
    result = investigate(demo_repo, "Why is committing a .env file with AWS keys dangerous?")
    assert any(f.category == "exposed_secret" for f in result.findings)
    assert ".env" in [f.file for f in result.findings]


def test_reviewer_flags_seeded_diff(demo_repo):
    from app.agents.pr_reviewer import review
    diff = (
        "diff --git a/app/services/orders.py b/app/services/orders.py\n"
        "+++ b/app/services/orders.py\n"
        "@@ -12,6 +12,9 @@\n"
        "+    sql = f\"SELECT * FROM orders WHERE note = '{note}'\"\n"
        "+    return db.query_all(sql)\n"
    )
    result = review(demo_repo, diff)
    cats = {f.category for f in result.findings}
    assert "sql_injection" in cats
    f = next(x for x in result.findings if x.category == "sql_injection")
    assert f.severity == "HIGH"
    assert f.file == "app/services/orders.py"


def test_reviewer_detects_removed_auth(demo_repo):
    from app.agents.pr_reviewer import review
    diff = (
        "diff --git a/app/middleware/auth.py b/app/middleware/auth.py\n"
        "+++ b/app/middleware/auth.py\n"
        "@@ -20,6 +20,8 @@\n"
        "-    payload = decode_token(auth_header.removeprefix(\"Bearer \").strip())\n"
        "+    payload = json.loads(base64.b64decode(auth_header.split(\".\")[1]))\n"
    )
    result = review(demo_repo, diff)
    assert any(f.category == "removed_auth" for f in result.findings)


def test_reviewer_no_false_positive_on_constants(demo_repo):
    """f-strings interpolating SCREAMING_CASE constants are parameterized-ish, not SQLi."""
    from app.agents.pr_reviewer import review
    diff = (
        "diff --git a/app/services/users.py b/app/services/users.py\n"
        "+++ b/app/services/users.py\n"
        "@@ -10,6 +10,8 @@\n"
        "+    rows = db.query_all(f\"SELECT {USER_COLUMNS} FROM users WHERE id = ?\", (uid,))\n"
    )
    result = review(demo_repo, diff)
    assert not any(f.category == "sql_injection" and "USER_COLUMNS" in f.snippet
                   for f in result.findings)


def test_verification_loop_catches_and_patches_missing_validation(demo_repo):
    from app.agents.test_generator import generate_tests
    result, v = generate_tests(demo_repo, "calculate_invoice")
    assert v.total >= 6
    assert v.status in ("validated", "validated_after_fix", "rejected")
    # iteration 1 must expose the unvalidated discount
    assert "missing_validation" in (v.iterations[0].get("failure_classes") or {}) \
        or v.status == "validated"
    # and the loop either validated directly or after proposing a patch
    if v.status == "validated_after_fix":
        assert v.patch and "discount" in v.patch["code"]
        assert v.passed == v.total


def test_generated_test_module_is_utf8(demo_repo, monkeypatch):
    """Windows regression: generated tests must be written as UTF-8.

    On Windows the default file encoding is cp1252. The generated module
    contains an em-dash, so a locale-encoded write produced a file Python
    refuses to import (SyntaxError: Non-UTF-8 code) -> pytest collection
    error -> failure class 'crash' -> verdict 'rejected'. Emulate the
    Windows default encoding here to guard the fix.
    """
    import builtins

    real_open = builtins.open

    def windows_open(file, mode="r", *args, **kwargs):
        if "b" not in mode and kwargs.get("encoding") is None:
            kwargs["encoding"] = "cp1252"
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", windows_open)
    from app.agents.test_generator import generate_tests
    _result, v = generate_tests(demo_repo, "calculate_invoice")
    assert v.status in ("validated", "validated_after_fix")
    assert v.total >= 6 and v.passed == v.total


def test_zero_test_run_is_never_validated(demo_repo, monkeypatch):
    """A sandboxed run that executes ZERO tests must not report 'validated'.

    Caught by CI on GitHub's hosted runners: they have a live Docker daemon,
    so auto mode selected the container sandbox whose stock image lacks
    pytest — the empty run sailed through the old `failed == 0 and
    errors == 0` acceptance check as a false VERIFIED verdict.
    """
    from app.agents import test_generator as tg
    from app.verification.loop import TestRun

    def fake_run_pytest(executor, workspace, test_rel, timeout):
        return TestRun(passed=0, failed=0, errors=0, failed_tests=[],
                       output="No module named pytest", exit_code=1)

    monkeypatch.setattr(tg, "run_pytest", fake_run_pytest)
    _result, v = tg.generate_tests(demo_repo, "calculate_invoice")
    assert v.status == "error", "zero-test runs must be reported as errors"
    assert v.passed == 0
    assert "no_tests_run" in (v.iterations[0].get("failure_classes") or {})
    assert "could not execute any tests" in v.summary

"""CodeGraph: call chains, callers, dependents, impact, route tracing, tests."""


def test_trace_route_users(demo_repo):
    tr = demo_repo.graph.trace_route("/api/users/{username}", method="GET")
    assert tr["route"].handler == "get_user"
    chain = [(h["symbol"], h["file"]) for h in tr["chain"]]
    assert ("get_user_by_username", "app/services/users.py") in chain
    assert ("query_one", "app/repositories/db.py") in chain


def test_trace_route_prefers_http_method(demo_repo):
    g = demo_repo.graph
    tr = g.trace_route("/api/products", method="POST")
    assert tr["route"].handler == "create_product"
    tr2 = g.trace_route("/api/products", method="GET")
    assert tr2["route"].handler == "list_products"


def test_callers_of_get_user_by_username(demo_repo):
    callers = demo_repo.graph.callers("app/services/users.py", "get_user_by_username")
    assert ("app/routes/users.py", "get_user") in callers
    assert ("app/auth/service.py", "authenticate") in callers


def test_file_dependents(demo_repo):
    deps = demo_repo.graph.file_dependents.get("app/services/users.py", set())
    assert "app/routes/users.py" in deps
    assert "app/auth/service.py" in deps


def test_transitive_impact(demo_repo):
    impact = demo_repo.graph.impact("app/repositories/db.py")
    assert "app/services/users.py" in impact      # direct
    assert "app/routes/users.py" in impact        # transitive


def test_per_alias_submodule_edges(demo_repo):
    """`from app.routes import orders, products, users` links the actual modules."""
    deps = demo_repo.graph.file_dependencies.get("app/main.py", set())
    assert "app/routes/orders.py" in deps
    assert "app/routes/users.py" in deps


def test_tests_for_files(demo_repo):
    tests = demo_repo.graph.tests_for_files(["app/utils/invoice.py"])
    assert "tests/test_invoice.py" in tests
    assert "app/utils/invoice.py" not in tests    # never reports the target itself

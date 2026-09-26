#!/usr/bin/env python3
"""RepoPilot demo — runs the five agents against the bundled demo repository
and prints a real transcript. Used to produce docs/DEMO_OUTPUT.md."""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
logging.basicConfig(level=logging.WARNING)

from app.config import get_settings
from app.repo_manager import RepoManager
from app.agents.supervisor import run_pipeline


def rule(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78 + "\n")


def main() -> None:
    repo = RepoManager(get_settings()).demo_repo()
    print(f"RepoPilot demo — repository: {repo.name}")
    print(f"LLM provider: heuristic (offline) — structured findings are deterministic")

    rule("1) REPOSITORY ANALYST — 'What is the architecture of this repository?'")
    out = run_pipeline(repo, question="What is the architecture of this repository?")
    print(out["answer"])

    rule("2) CODE SEARCH — 'Where is JWT authentication implemented?'")
    out = run_pipeline(repo, question="Where is JWT authentication implemented?")
    print(out["answer"])

    rule("3) ISSUE INVESTIGATION — 'Why might GET /api/users/{username} return HTTP 500?'")
    out = run_pipeline(repo, question="Why might GET /api/users/{username} return HTTP 500?")
    print(out["answer"])

    rule("4) PR REVIEW — seeded diff (SQL injection + bare except + hardcoded token)")
    diff = """diff --git a/app/services/orders.py b/app/services/orders.py
+++ b/app/services/orders.py
@@ -12,6 +12,14 @@ def list_orders(status: str = ""):
     if not status:
         return db.query_all("SELECT id, username, total, status FROM orders ORDER BY created_at DESC")
+    sql = f"SELECT id, username, total, status FROM orders WHERE status = '{status}' LIMIT 100"
+    return db.query_all(sql)
+
+def export_orders(username: str):
+    try:
+        return db.query_all(f"SELECT * FROM orders WHERE username = '{username}'")
+    except Exception:
+        pass
+
+ADMIN_TOKEN = "sk-admin-9f8e7d6c5b4a3210fedcba9876543210"
"""
    out = run_pipeline(repo, diff=diff, question="review this pull request")
    print(out["answer"])

    rule("5) TEST GENERATION + VERIFICATION LOOP — 'generate tests for calculate_invoice'")
    out = run_pipeline(repo, question="generate tests for calculate_invoice",
                       target="calculate_invoice")
    print(out["answer"])
    v = out.get("verification") or {}
    if v.get("test_code"):
        print("\n--- generated test module " + "-" * 40)
        print(v["test_code"])

    rule("AGENT TRACE (from the last run)")
    for e in out.get("events", []):
        detail = {k: v for k, v in e.items() if k not in ("step", "ts")}
        print(f"  {e['step']:12} {detail}")


if __name__ == "__main__":
    main()

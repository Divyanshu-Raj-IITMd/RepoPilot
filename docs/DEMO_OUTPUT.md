RepoPilot demo — repository: ecommerce-api
LLM provider: heuristic (offline) — structured findings are deterministic

==============================================================================
1) REPOSITORY ANALYST — 'What is the architecture of this repository?'
==============================================================================

### Repository analysis

Repository: ecommerce-api
Languages: python (25 files)
Frameworks: FastAPI
Database: SQLite
Main entry: app/main.py
Authentication: app/auth/ (app/auth/__init__.py, app/auth/jwt.py)
API: app/routes/ (app/routes/__init__.py, app/routes/orders.py)
Business logic: app/services/ (app/services/__init__.py, app/services/orders.py)
Data access: app/repositories/ (app/repositories/__init__.py, app/repositories/db.py)
Models: app/models/ (app/models/__init__.py, app/models/models.py)
Tests: tests/__init__.py, tests/test_invoice.py, tests/test_jwt.py

28 files, 587 lines, 49 symbols, 11 HTTP endpoints.

==============================================================================
2) CODE SEARCH — 'Where is JWT authentication implemented?'
==============================================================================

### Code search

Found 3 matching location(s):
1. app/auth/service.py:1-27 — file: app/auth/service.py (python)
   why: strong term overlap with the question; semantic similarity; module structure overview
2. app/auth/jwt.py:34-50 — decode_token
   context: file: app/auth/jwt.py
   why: strong term overlap with the question
3. app/middleware/auth.py:11-23 — auth_middleware
   context: async def auth_middleware(request: Request, call_next):
   why: calls decode_token (app/auth/jwt.py) — part of the execution flow

==============================================================================
3) ISSUE INVESTIGATION — 'Why might GET /api/users/{username} return HTTP 500?'
==============================================================================

### Investigation

Investigation: Why might GET /api/users/{username} return HTTP 500?

Endpoint: GET /api/users/{username} -> get_user (app/routes/users.py:25)
Call chain:
  └─ get_user  (app/routes/users.py:25)
    └─ get_user_by_username  (app/services/users.py:15)
      └─ query_one  (app/repositories/db.py:66)
      └─ _to_user  (app/services/users.py:38)
        └─ connect  (app/repositories/db.py:42)

Ranked hypotheses (6):
1. [HIGH] Possible None dereference: `user` is used without a None check — app/routes/users.py:27
   `user` is assigned from `user_service.get_user_by_username(username)` which can return None (assignment at line 26); line 27 then uses `user` directly, which raises TypeError/AttributeError when None.
2. [MEDIUM] GET /api/users/{username}: handler has no error handling — app/routes/users.py:25
   Any exception from the service/data layers escapes as a raw HTTP 500 instead of a precise status code.
3. [MEDIUM] GET /api/users/login: handler has no error handling — app/routes/users.py:11
   Any exception from the service/data layers escapes as a raw HTTP 500 instead of a precise status code.
4. [MEDIUM] GET /api/users: handler has no error handling — app/routes/users.py:19
   Any exception from the service/data layers escapes as a raw HTTP 500 instead of a precise status code.
5. [MEDIUM] POST /api/users: field(s) used without validation: email, password, username — app/routes/users.py:31
   Request-body fields reach the service layer without any validate_/assert/check call — malformed input propagates downstream (or causes 500s).

Related tests: none found for the involved files (coverage gap).
Question mentions status 500: unhandled exceptions in the chain above would surface as HTTP 500.

==============================================================================
4) PR REVIEW — seeded diff (SQL injection + bare except + hardcoded token)
==============================================================================

### PR review

Reviewed 1 changed file(s): app/services/orders.py

Findings: 4 HIGH / 3 MEDIUM / 0 LOW

[HIGH] SQL built via string interpolation (injection risk) — app/services/orders.py:10
    sql = f"SELECT id, username, total, status FROM orders WHERE status = '{status}' ORDER BY created_at DESC"
[HIGH] Potential SQL injection risk — app/services/orders.py:14
    sql = f"SELECT id, username, total, status FROM orders WHERE status = '{status}' LIMIT 100"
[HIGH] Potential SQL injection risk — app/services/orders.py:19
    return db.query_all(f"SELECT * FROM orders WHERE username = '{username}'")
[HIGH] Hardcoded secret assignment committed in the diff — app/services/orders.py:23
    ADMI*** = "sk-a***"
[MEDIUM] No unit test for the changed code — app/services/orders.py:14
    sql = f"SELECT id, username, total, status FROM orders WHERE status = '{status}' LIMIT 100"
[MEDIUM] Broad exception handler swallows errors — app/services/orders.py:20
    except Exception:
[MEDIUM] Query executed inside a loop (N+1 pattern) — app/services/orders.py:28
    db.execute(

==============================================================================
5) TEST GENERATION + VERIFICATION LOOP — 'generate tests for calculate_invoice'
==============================================================================

### Test generation & verification

VERIFIED after correction — final run: 8/8 tests passed. A validation patch was proposed, applied in the sandbox and re-verified.
Proposed patch (validate rate-like parameters before computing):
    if not 0 <= discount <= 1:
        raise ValueError("discount must be between 0 and 1")
Loop executed 2 iterations: 6/8 -> 8/8

--- generated test module ----------------------------------------
"""Generated by RepoPilot's Test Generation Agent.

Target: calculate_invoice — categories: boundary, empty, invalid, large, normal, zero
"""
import pytest

from app.utils.invoice import calculate_invoice


def test_docstring_example():
    assert calculate_invoice([{"price": 10, "quantity": 2}], 0.1) == 18.0

def test_normal():
    result = calculate_invoice(items=[{"price": 10, "quantity": 2}], discount=0.0)
    assert result >= 0, f"expected non-negative total, got {result!r}"

def test_empty_items():
    result = calculate_invoice(items=[], discount=0.0)
    assert result >= 0, f"expected non-negative total, got {result!r}"

def test_large_items():
    result = calculate_invoice(items=[{"price": 999999, "quantity": 100000}], discount=0.0)
    assert result is not None or True  # smoke: must not raise

def test_zero_discount():
    result = calculate_invoice(items=[{"price": 10, "quantity": 2}], discount=0)
    assert result >= 0, f"expected non-negative total, got {result!r}"

def test_boundary_discount_full():
    result = calculate_invoice(items=[{"price": 10, "quantity": 2}], discount=1)
    assert result >= 0, f"expected non-negative total, got {result!r}"

def test_invalid_discount_above_one():
    with pytest.raises((ValueError, TypeError)):
        calculate_invoice(items=[{"price": 10, "quantity": 2}], discount=1.5)

def test_invalid_discount_negative():
    with pytest.raises((ValueError, TypeError)):
        calculate_invoice(items=[{"price": 10, "quantity": 2}], discount=-0.5)


==============================================================================
AGENT TRACE (from the last run)
==============================================================================


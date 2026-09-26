# RepoPilot — What We Built and How

This document explains, end to end, what exists in this repository, how each part works, and why it was built that way. It is written so you can re-derive every design decision.

## The one-sentence idea

An AI coding assistant is only trustworthy if its **facts come from deterministic code analysis** and its **claims are validated by execution** — so RepoPilot is built as: *repository → AST + dependency graph → semantic index → specialized agents → sandboxed execution → verification → evidence-backed answer*.

The LLM is deliberately the **last** and **least** important component: it narrates evidence, it never creates it.

## What we built (layers, in pipeline order)

### 1. Ingestion — "get the repo safely"
- `git clone --depth 1` for URLs (120 s timeout, size guard) or local paths.
- A walker with ignore rules, a 200 KB/file cap, a 6 000-file ceiling and binary sniffing — indexing must never be a denial-of-service on a huge repo.
- A dotfile quirk worth knowing: `os.path.splitext(".env")` returns *no* extension, so `.env` files are matched by name explicitly (and they matter — see security).
- Detection: frameworks/databases from dependency files + import markers; **directory roles** (`auth`, `routes`, `services`, `repositories`, …) from path names. The Repository Analyst renders these directly — that's why its output looks like a senior engineer's map of the codebase.

### 2. AST parsing — "real structure, not text"
- Python via the stdlib `ast` module: symbols with signatures/docstrings/decorators, imports with aliases, call sites, HTTP routes from decorators, and two subtle signals we exploit later:
  - **explicit `return None`** — `return None` parses as `Constant(value=None)`, not a bare `return`; both are tracked. This is the fuel for the None-dereference detector.
  - **documented `raise`s** — if a function documents `ValueError`, generated tests for invalid input *expect* that error.
- Other languages: heuristic regex parser; optional Tree-sitter upgrade for JS/TS (graceful degradation is explicit, not hidden).

### 3. CodeGraph — "the part that makes it more than RAG"
- Dotted-module ↔ file resolution, including the tricky `from app.services import users as user_service` case: `app.services` resolves to `__init__.py`, so we *prefer the submodule* `app/services/users.py` and record **per-alias edges** (so `from app.routes import orders, products, users` links all three modules).
- Call resolution through import aliases: `user_service.get_user_by_username(...)` → `(app/services/users.py, get_user_by_username)`.
- Queries: route tracing (BFS from a handler), callers/callees, file dependents, **transitive impact**, tests-for-files.
- This powers the answers that pure-RAG systems cannot give exactly: call chains, "who calls X", "what breaks if I change db.py".

### 4. Indexing — "semantic recall"
- Chunks: symbols (with headers), file overviews, endpoint chunks, docs, and **redacted config** files.
- Two embedders: deterministic hashing TF-IDF (4096-dim, CRC32 features, plural stemming — `tokens` → `token`) so everything works offline/CI; sentence-transformers when installed.
- FAISS when available, exact numpy otherwise; persisted to disk.

### 5. Hybrid retrieval — "rank like an engineer"
- 0.55·dense + 0.45·lexical + path/symbol boosts + **verb-intent boosts** ("where are tokens **created**" boosts `encode_*`/`create_*` symbols) + graph expansion of the top files' import neighbours.
- Every hit records *why* it matched — that reason string flows into the citation shown in the UI.

### 6. The supervisor & agents — "specialists, not one prompt"
- A LangGraph `StateGraph`: `START → supervisor → {analyst | search | investigate | review | testgen}` with `testgen → verify → supervisor`. If `langgraph` isn't installed, a 100-line MiniGraph with identical semantics (nodes/edges/conditional edges/append reducers) runs the same functions.
- Routing is **deterministic keyword/regex classification**. An intent router does not need an LLM, and reproducibility is required by the eval suite.
- Architecture questions are recognized as *repo-scoped* and go to the analyst; dependency questions ("which files import X") are answered **directly from the graph**, with retrieval as backup.

### 7. Static risk patterns — "findings, not vibes"
Shared by the investigator and the reviewer, each check is a small analyzer with a rationale string:
- None-dereference: variable assigned from a may-return-None call (tracked via AST) then used without a guard
- SQL injection: f-string/format/concatenation into SQL **with user-input interpolation** — `f"SELECT {USER_COLUMNS}…"` with bound params is *not* flagged (constant-interpolation analysis)
- bare `except: pass`, dangerous calls (`eval`/`exec`/`os.system`/`shell=True`), mutable defaults, weak hashes in password contexts
- handlers without error handling; **unvalidated request-body fields** (fields accessed from `body[...]` minus fields passed through `validate_*` calls); unguarded rate-like parameters (`discount`/`rate`/`percent`); N+1 queries in loops
- reviewer-specific: removed auth lines (with a *replacement* check so refactors aren't flagged), breaking signature changes, secrets in added lines, missing tests for changed code, and repo-context checks **restricted to diff-touched lines** so pre-existing issues aren't blamed on the PR.

### 8. Security layer — "a legitimate AI-security story"
- Ingest-time secret scan (AWS keys, DSNs with passwords, private keys, `*_TOKEN` assignments, …).
- **Redaction before any remote LLM call**; `.env` indexed only in redacted form.
- Execution in an ephemeral Docker container (`--network none --read-only --cap-drop ALL --memory 512m --pids-limit 64`) or a hardened subprocess fallback (env whitelist + rlimits + timeout + scratch workspace), with the executor name reported in every result.

### 9. The verification loop — "validate before you trust"
For a target function: signature analysis (including **body-derived guards**: `if quantity < 1: raise` becomes a legal-minimum boundary the tests assert on both sides of) → category matrix (normal/empty/zero/negative/large/boundary/invalid + docstring examples + encode↔decode round-trips) → pytest module → **sandboxed run** → failure classification (`missing_validation` / `value_bug` / `crash` / `assertion`) → optional guard patch applied in the sandbox → re-run → verdict (`validated` / `validated_after_fix` / `rejected`) with the full log.

Expectations are *properties* (non-negative totals, documented errors must raise, round-trips must verify) — never invented expected values. That's why a failing test is a **real finding about the code**, not a broken test.

### 10. Evaluation — "measure it, then quote it"
- 104 hand-written questions with gold files/keywords/findings (20 per spec category), executed against the live pipeline.
- Metrics: retrieval Recall@5/@10, citation correctness, task success, latency p50/p95.
- Results in `eval/results.md` — the README quotes the same run. Real numbers only.

## How the pieces proved themselves (real runs)

- **Investigator**: "Why might `GET /api/users/{username}` return HTTP 500?" → traced `get_user → get_user_by_username → query_one`, ranked hypothesis #1: *None dereference at `app/routes/users.py:27`* — exactly the seeded bug, with the assignment line, the usage line and the rationale.
- **Reviewer** on a seeded diff: 4 HIGH / 3 MEDIUM — SQL injection ×3, hardcoded `ADMIN_TOKEN`, bare except, N+1 in a loop, missing tests.
- **Test generator**: 8 tests for `calculate_invoice` → 6/8 → both failures classified `missing_validation` → guard patch proposed → re-run → **8/8 validated after fix**.
- **Evaluator**: 104/104 task success offline, no LLM at all.

## Why this architecture (interview-ready reasoning)

1. **Grounded by construction** — citations come from the retriever/graph; the LLM can't hallucinate files it wasn't given.
2. **Works offline** — heuristic mode keeps the entire product functional (and CI-able) with zero API keys; providers are additive, not load-bearing.
3. **Deterministic where it matters** — routing, findings and verdicts are reproducible; that's what makes an evaluation suite meaningful.
4. **Security as a first-class layer** — secrets never reach a model; generated code never runs unsandboxed.
5. **Measurable** — recall, success and latency are tracked per category; every README claim is a run output.

## What to say when asked "isn't this just RAG?"

No — RAG retrieves text and asks an LLM to answer. RepoPilot:
- builds a **typed graph** (modules, symbols, call edges, routes) and answers dependency/impact questions *exactly*;
- runs **static analyzers** whose findings are the answer's substance;
- **executes** generated tests in a sandbox and reports pass/fail verdicts;
- and only then lets an (optional) LLM write the prose.

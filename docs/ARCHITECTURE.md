# Architecture

RepoPilot is a pipeline-first system: **facts are computed deterministically, the LLM only narrates them.** This document explains each layer and why it is built that way.

## 1. Ingestion (`app/ingestion/`)

`clone_or_load()` shallow-clones a git URL (depth 1, 120 s timeout) or accepts a local path. `walk_repository()` enumerates files with:

* ignore rules (`.git`, `node_modules`, `venv`, `__pycache__`, build dirs, …)
* per-file size cap (200 KB) and a 6 000-file hard limit
* binary detection (extension + NUL-byte sniffing)
* dotfile handling (`os.path.splitext(".env")` has no extension — handled explicitly)

`detect_summary()` classifies the repository: languages by extension count, frameworks/databases by dependency-file and import markers (FastAPI, Flask, Django, Next.js, Express, Gin, Spring, SQLAlchemy, Prisma, …), entry-point candidates, and **directory roles** (`app/auth` → authentication, `app/routes` → api, `app/services` → business logic, …) which the Repository Analyst renders directly.

## 2. Parsing (`app/parsing/`)

**Python** uses the stdlib `ast` module — no dependencies, full fidelity:

* symbols: functions/classes/methods with signatures, docstrings, decorators, parents
* **explicit `return None` tracking** (the key signal for the None-dereference detector)
* `raise` statements (drives test expectations: documented errors must be raised)
* imports (including nested-in-function imports) with alias maps
* call sites as written (`user_service.get_user_by_username(...)`)
* **HTTP routes from decorators** (`@router.get("/api/users/{username}")`)

**JS/TS/Go/others** get a heuristic regex parser (functions, imports, Express routes). Installing the optional `tree-sitter` + grammar packages upgrades JS/TS to real AST parsing; the system degrades gracefully either way.

## 3. CodeGraph (`app/graph/code_graph.py`)

The dependency layer built once per repository:

* **module resolution** — dotted module ↔ file, including `from pkg import submodule` (prefers `pkg/submodule.py` over `pkg/__init__.py`, with per-alias edges so `from app.routes import orders, products, users` links all three route modules)
* **call-edge resolution** — `user_service.get_user_by_username(...)` resolves through the import-alias map to `(app/services/users.py, get_user_by_username)`; `self.x` resolves within the enclosing class
* **queries**: `trace_route(path, method)` (BFS from the route handler), `callers/callees`, `file_dependents`, `impact(file)` (transitive blast radius), `tests_for_files` (which tests import or mention these files/symbols)

This is what makes answers like *"`app/repositories/db.py` is imported by … / changing it impacts these 6 files"* exact rather than guessed.

## 4. Indexing (`app/indexing/`)

Chunk types: **symbol** (function/class with a header: file, signature, docstring, decorators), **file** (structural overview: symbols, imports, dependencies), **route** (endpoint → handler), **doc** (markdown), **config** (`.env`/yaml/toml — **redacted** before embedding).

Embeddings:

* `HashingTfidfEmbedder` — offline default. Identifiers are split (camelCase/snake_case, plural-stemmed), hashed with CRC32 into a 4 096-dim TF-IDF vector, L2-normalized. Deterministic, dependency-free, CI-friendly.
* `SentenceTransformerEmbedder` — `all-MiniLM-L6-v2` when `sentence-transformers` is installed.

Vector store: FAISS `IndexFlatIP` when available, otherwise exact numpy dot-product; persisted to `.repopilot/indexes/` with metadata.

## 5. Retrieval (`app/retrieval/retriever.py`)

Hybrid scoring per chunk:

```
score = 0.55 · cosine(dense) + 0.45 · min(lexical_overlap, 1)
        + path-token boosts + symbol-name boosts
        + verb-intent boosts ("created" → create_*/encode_*)
        + route-chunk boost for endpoint queries
        − 15% file-chunk penalty (prefer precise symbol chunks)
```

followed by **graph expansion**: 1-hop import-neighbours of the top files are pulled in at reduced weight. Every hit carries the *reason* it matched — that string becomes part of the citation, so the answer explains itself.

## 6. Agents (`app/agents/`)

State is a LangGraph `TypedDict` with an append-reducer for trace events. The **supervisor** classifies intent deterministically (reproducible routing is a feature — the eval suite depends on it) and dispatches:

| node | does |
|---|---|
| `analyst` | renders the RepoSummary (frameworks, DB, entry, layered dirs w/ example files, endpoints) |
| `search` | hybrid retrieval + per-file citation budget + **graph completion** (callers of top symbols) + **dependency questions answered straight from the CodeGraph** (`which files import X`, `who calls Y`, `what does Z depend on`) + test-coverage lookups |
| `investigate` | extracts route + HTTP method + status from the question → `trace_route` → static risk checks along the chain → ranked hypotheses; security questions surface the ingest-time secret scan |
| `review` | parses the unified diff, maps hunks to new-file line numbers, runs diff-level checks (SQLi with constant-vs-input interpolation analysis, secrets, bare except, dangerous calls, mutable defaults, removed auth, breaking signature changes, N+1-in-loop, TODO/style) + repo-context checks **restricted to touched lines** + missing-test detection |
| `testgen` | see verification loop |
| `verify` | gate node: emits the verdict event (validated / rejected) |

If `langgraph` is not installed, a 100-line `MiniGraph` with identical semantics (nodes, edges, conditional edges, list-append reducers) runs the same node functions — so CI and offline installs lose nothing.

**Narration:** each agent produces an `AgentResult` (summary, citations, findings, extras) *deterministically*. `narrate()` then asks the configured LLM to write prose over the evidence pack, falling back to a template renderer in heuristic mode. The LLM never adds citations.

## 7. Sandbox & security (`app/sandbox/`)

* `secret_scanner.py` — high-signal patterns (AWS `AKIA…`, Google `AIza…`, private keys, GitHub/Slack tokens, DSNs with passwords, `*_SECRET`/`*_TOKEN` assignments). `redact()` masks matches before any content leaves for a remote LLM; `.env` chunks are stored redacted.
* `DockerExecutor` — `docker run --rm --network none --read-only --tmpfs /tmp --memory 512m --cpus 1 --pids-limit 64 --cap-drop ALL --security-opt no-new-privileges`, repo copied into a scratch overlay.
* `SubprocessExecutor` — fallback: env whitelist, `RLIMIT_CPU/AS/NOFILE/NPROC/F-SIZE` via `preexec_fn`, hard timeout, scratch copy of the repo. Weaker isolation, always reported by name in results.

## 8. Verification loop (`app/verification/` + `agents/test_generator.py`)

1. AST-analyse the target's signature (params, annotations, defaults, docstring examples, documented raises)
2. derive the category matrix: normal / empty / zero / negative / large / boundary / invalid — expectations are *properties* (non-negative totals, documented errors must raise, encode↔decode round trips), never fabricated expected values
3. render a standalone pytest module and run it through the executor
4. parse and **classify failures**: `missing_validation` (DID NOT RAISE), `value_bug`, `crash`, `assertion`
5. if all failures are missing validation of rate-like parameters → propose a guard patch, apply it **in the sandbox copy only**, regenerate, re-run (max N iterations)
6. verdict: `validated` / `validated_after_fix` / `rejected`, with the full iteration log, patch and generated code attached

## 9. Evaluation (`app/evaluator/`)

104 hand-written questions over the demo repo across 6 categories (20 per spec category + 4 test-generation targets), each with gold files, expected answer keywords, and (for review) expected finding categories. The runner executes the **live pipeline** per question and measures:

* retrieval Recall@5/@10 (gold files in the retriever's top-k)
* citation correctness (share of citations on gold files)
* task success (correct agent route + gold files surfaced + keywords present / findings detected / verification verdict)
* latency p50/p95

Results are written to `eval/results.{md,json}` — the README numbers are from actual runs.

## 10. API & UI

FastAPI serves `/api/repos`, `/api/chat` (JSON), `/api/chat/stream` (SSE: each supervisor/tool/agent event streams live, then the final payload), `/api/review`, `/api/tests/generate`, `/api/eval/run`, `/api/health`. The Next.js app proxies `/api/*` to the backend (single origin), renders the agent trace timeline, clickable citations with real code snippets, the verification card (iterations, patch, generated tests), the findings table and the evaluation dashboard.

# RepoPilot — Agentic AI Software Engineering Assistant

**RepoPilot** is an AI-powered software engineering assistant that understands large codebases through repository analysis, semantic code retrieval and agentic workflows. It combines **AST-aware code indexing**, **RAG** and **specialized AI agents** to answer repository questions, trace dependencies, investigate issues, review pull requests and generate tests — with **file-level evidence and citations** for every answer.

Built as a full-stack, local-first system using **Next.js, FastAPI, LangGraph, FAISS/numpy, Tree-sitter (optional), Docker and locally hosted LLMs through Ollama**. It emphasizes grounded responses, automated validation, secure code execution and measurable evaluation rather than free-form LLM generation.

> **This is not a chatbot with RAG.** Every answer is produced by deterministic code analysis (AST parsing, a dependency graph, static security/correctness checks, sandboxed test execution). The LLM — when one is configured — only *narrates* evidence the pipeline already found. It cannot invent citations. When no LLM is available at all, RepoPilot runs fully offline in *heuristic mode* and still answers with real evidence.

---

## What it does

| Agent | Question it answers | Evidence it produces |
|---|---|---|
| **Repository Analyst** | "What is the architecture of this repo?" | frameworks, DB, entry point, layered directory map, endpoint inventory |
| **Code Search** | "Where is JWT authentication implemented?" | ranked files + line ranges + code context + *why each file matched*, plus a call-graph flow |
| **Issue Investigator** | "Why might `GET /api/users/{username}` return HTTP 500?" | endpoint → controller → service → DB call chain, ranked hypotheses with file:line |
| **PR Reviewer** | paste a `git diff` | severity-tagged findings: security, correctness, performance, maintainability, tests, breaking changes |
| **Test Generator** | "generate tests for `calculate_invoice`" | a category matrix (normal/empty/zero/negative/large/boundary/invalid) **executed in a sandbox**, with a verdict |

### The verification loop (the core differentiator)

AI-generated output is never trusted by default:

```
LLM / generator
      ↓
proposed tests / patch
      ↓
static checks  →  sandboxed pytest run  →  failure classification
      ↓                                              ↑
      └────────── propose correction ────────────────┘
      ↓
   verdict:   ✅ validated (8/8 passed)   ·   ⛔ rejected (2/8 passed)
```

A real run against the bundled demo repo (the function has an unvalidated `discount` parameter):

```
VERIFIED after correction — final run: 8/8 tests passed. A validation patch
was proposed, applied in the sandbox and re-verified.
Proposed patch (validate rate-like parameters before computing):
    if not 0 <= discount <= 1:
        raise ValueError("discount must be between 0 and 1")
Loop executed 2 iterations: 6/8 -> 8/8
```

### Security layer

* **Secret scanning at ingest** — AWS keys, DB URLs with passwords, private keys, hardcoded `*_SECRET`/`*_TOKEN` assignments (the demo repo ships a committed `.env` that gets flagged).
* **Redaction before any LLM call** — secret-looking spans are replaced with `***REDACTED***` before content is sent to any remote provider; `.env` files are indexed only in redacted form.
* **Sandboxed execution** — generated tests run in an ephemeral container (`docker run --network none --read-only --cap-drop ALL --memory 512m --pids-limit 64`) or, where Docker is unavailable (CI), a hardened subprocess: environment whitelist, `rlimit` caps (CPU/AS/NOFILE/NPROC), scratch-workspace copies and hard timeouts. The API always reports which executor ran.

---

## Evaluation (real numbers, offline heuristic mode)

Run with `make eval`. Full per-question results: [`eval/results.md`](eval/results.md). Dataset: **104 hand-written questions with gold answers derived from reading the demo repo** — 20 per spec category (architecture, code search, dependency tracing, bug investigation, PR review) plus 4 test-generation targets. The evaluator always runs the deterministic pipeline (LLM narration disabled), so metrics are reproducible and identical with or without Ollama/Groq/Gemini configured.

| Metric | Result |
|---|---|
| **Agent task success** | **100%** (104/104) |
| Retrieval Recall@5 / @10 | 0.79 / 0.82 |
| Citation correctness | 0.51 |
| Latency p50 / p95 | 9 ms / 22 ms |
| Backend test suite | 41/41 passing |

| Category | Questions | Task success | Recall@5 |
|---|---|---|---|
| architecture | 20 | 1.00 | 0.50 |
| code search | 20 | 1.00 | 0.98 |
| dependency tracing | 20 | 1.00 | 0.77 |
| bug investigation | 20 | 1.00 | 0.95 |
| PR review | 20 | 1.00 | 0.55 |
| test generation | 4 | 1.00 | 1.00 |

(Recall is retrieval-level: "did the gold file appear in the top-k of the hybrid retriever". Task success is end-to-end: correct route + correct files + correct content in the final answer. PR-review recall is low by construction — a diff names one file while gold includes cross-file evidence the reviewer adds.)

A full transcript of all five agents running against the demo repo: [`docs/DEMO_OUTPUT.md`](docs/DEMO_OUTPUT.md).

---

## Architecture

```
                         RepoPilot
                            │
                            ▼
                    ┌───────────────┐
                    │   Next.js UI  │  chat · PR review · test gen · eval dashboard
                    └───────┬───────┘
                            │  /api/* (REST + SSE agent trace)
                            ▼
                    ┌───────────────┐
                    │   FastAPI     │
                    │   Backend     │
                    └───────┬───────┘
                            ▼
                  ┌───────────────────┐
                  │ LangGraph Agent   │
                  │    Supervisor     │   (dependency-free MiniGraph fallback)
                  └─────────┬─────────┘
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Repo Analyst │    │ Code Search  │    │ Issue Agent  │
└──────┬───────┘    └──────┬───────┘    └──────┬───────┘
       │      ┌────────────┴────────────┐       │
       │      ▼                         ▼       │
       │ ┌──────────────┐      ┌──────────────┐ │
       │ │ PR Reviewer  │      │ Test Agent   │ │
       │ └──────────────┘      └──────┬───────┘ │
       │                             ▼         │
       │                    ┌───────────────┐   │
       │                    │ Verification  │   │
       │                    │ loop (sandbox)│   │
       │                    └───────────────┘   │
       └────────────┬────────────────────────────┘
                    ▼
          ┌──────────────────┐
          │  Code Retrieval  │  hybrid: dense vectors + lexical overlap +
          │  FAISS / numpy   │  symbol boosts + graph expansion
          └────────┬─────────┘
                   ▼
          ┌──────────────────┐        ┌──────────────────┐
          │  AST + Code Graph│        │  Secret scanner  │
          │  (Python ast,    │        │  + redaction     │
          │   Tree-sitter *) │        └──────────────────┘
          └────────┬─────────┘
                   ▼
          ┌──────────────────┐
          │  LLM (optional)  │  Ollama (local) · Groq · Gemini · OpenRouter
          │  narration only  │  · or fully-offline heuristic mode
          └──────────────────┘
```

\* Tree-sitter upgrades JS/TS parsing when installed; out of the box Python uses the stdlib `ast` module and other languages use a heuristic parser.

Deep dive: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · How & why it was built: [`docs/EXPLANATION.md`](docs/EXPLANATION.md)

---

## Quickstart

### 0. Prerequisites
Python 3.10+, Node 18+, git. (Docker optional but recommended for the sandbox.)

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000  (proxies /api to :8000)
```

### 3. Use it

Click **“Load bundled demo repo”** — or point it at any GitHub URL / local path. Try:

* *“Why might GET /api/users/{username} return HTTP 500?”*
* *“Where is JWT authentication implemented?”*
* *“Which files import app/services/users?”*
* *“generate tests for calculate_invoice”*
* PR Review tab → **Use seeded sample** → Review diff

### LLM modes (all free)

```bash
# nothing configured → offline heuristic mode (works out of the box)

# 100% local:
ollama pull qwen2.5-coder:7b        # or any model
export REPOPILOT_LLM_PROVIDER=ollama

# free-tier APIs (auto-detected from env):
export GROQ_API_KEY=...             # llama-3.3-70b-versatile
export GEMINI_API_KEY=...           # gemini-2.0-flash
export OPENROUTER_API_KEY=...       # free community models
```

Details & provider notes: [`docs/LLM_PROVIDERS.md`](docs/LLM_PROVIDERS.md).

### Docker (optional)

```bash
docker compose up backend ollama     # API on :8000 + local models
```

---

## Repo layout

```
backend/
  app/
    ingestion/     cloner, safe walker, language/framework detectors
    parsing/       Python AST parser, heuristic parser, optional Tree-sitter
    graph/         CodeGraph: call chains, dependents, impact, route table
    indexing/      chunker + embedders (hashing TF-IDF / sentence-transformers)
                   + vector store (FAISS or numpy, persisted)
    retrieval/     hybrid retriever (dense + lexical + symbol + graph)
    agents/        supervisor (LangGraph) + 5 specialist agents + risk patterns
    sandbox/       secret scanner/redaction, Docker & subprocess executors
    verification/  the generate → run → classify → patch → re-run loop
    evaluator/     dataset (104 q), metrics, runner  →  eval/results.md
    api/           FastAPI routes (+ SSE agent-trace streaming)
  tests/           34 tests (parsing, graph, retrieval, agents, sandbox, eval)
frontend/          Next.js 14 + TypeScript + Tailwind (chat, review, tests, eval)
demo-repos/        ecommerce-api — a realistic FastAPI repo with seeded defects
eval/              real evaluation results (results.md / results.json)
docs/              ARCHITECTURE, EXPLANATION, LLM_PROVIDERS, DEMO_OUTPUT
.github/           CI: ruff + pytest + evaluation run on every push
```

## Development

```bash
make test          # backend pytest suite
make eval          # run the 104-question evaluation suite
make lint          # ruff
make demo          # print a full transcript of all five agents
make dev           # backend on :8000
```

## Honest limitations

* Non-Python repos get heuristic parsing (regex) — symbol-level call graphs are Python-first; Tree-sitter upgrades JS/TS when installed.
* The subprocess sandbox (no Docker) is *hardened*, not *isolated* — use the Docker executor for untrusted repos.
* Answer correctness is measured against a hand-written gold set on one demo repo; extending the dataset to more repos is the main next step (see roadmap).
* Hashing TF-IDF embeddings are weaker than neural ones — install `sentence-transformers` for better semantic recall; hybrid + graph signals compensate either way.

## Roadmap

1. Multi-repo evaluation set (100+ questions across languages)
2. Tree-sitter grammars for Go/Java/Rust + cross-language call graphs
3. Qdrant backend option + incremental re-indexing on git push
4. PR Review agent posting comments via GitHub webhooks
5. LLM-judged answer-correctness scoring in the evaluator (currently keyword/gold-file based)

## License

MIT

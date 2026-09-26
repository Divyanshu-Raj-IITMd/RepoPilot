"""REST + SSE routes."""

from __future__ import annotations

import json
import queue as queue_mod
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.agents.state import EventTap
from app.agents.supervisor import run_pipeline
from app.api.schemas import ChatIn, EvalIn, RepoIn, ReviewIn, TestGenIn
from app.llm import get_llm
from app.repo_manager import RepoManager

router = APIRouter(prefix="/api")
_pool = ThreadPoolExecutor(max_workers=4)


def manager() -> RepoManager:
    return router.state.manager  # type: ignore[attr-defined]


def _repo_or_404(repo_id: str):
    repo = manager().get(repo_id)
    if repo is None:
        raise HTTPException(404, f"repo '{repo_id}' not found — POST /api/repos first")
    return repo


# ------------------------------------------------------------------- repos

@router.post("/repos")
def add_repo(body: RepoIn):
    try:
        repo = manager().ingest(body.source, repo_id=body.repo_id, name=body.name)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"ingestion failed: {exc}") from exc
    return repo.overview()


@router.post("/repos/demo")
def add_demo_repo():
    try:
        repo = manager().demo_repo()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(400, f"demo repo ingestion failed: {exc}") from exc
    return repo.overview()


@router.get("/repos")
def list_repos():
    return {"repos": manager().list_repos()}


@router.get("/repos/{repo_id}")
def get_repo(repo_id: str):
    return _repo_or_404(repo_id).overview()


# -------------------------------------------------------------------- chat

@router.post("/chat")
def chat(body: ChatIn):
    repo = _repo_or_404(body.repo_id)
    final = run_pipeline(repo, question=body.message, target=body.target or "")
    return _final_payload(final)


@router.post("/chat/stream")
def chat_stream(body: ChatIn):
    repo = _repo_or_404(body.repo_id)

    def event_stream():
        q: queue_mod.Queue = queue_mod.Queue()

        def run():
            # the tap is thread-local: bind it inside the worker thread that
            # actually executes the graph
            EventTap.attach(q)
            try:
                final = run_pipeline(repo, question=body.message, target=body.target or "")
                q.put(("final", final))
            except Exception as exc:  # noqa: BLE001
                q.put(("error", str(exc)))
            finally:
                EventTap.detach()
                q.put(None)

        worker = _pool.submit(run)
        try:
            while True:
                item = q.get(timeout=300)
                if item is None:
                    break
                if isinstance(item, tuple):
                    kind, payload = item
                else:  # raw trace event from the EventTap
                    kind, payload = "trace", item
                yield _sse(kind, payload)
            worker.result(timeout=30)
        except GeneratorExit:
            pass

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(kind: str, payload) -> str:
    event = {"event": kind, "data": payload}
    return f"data: {json.dumps(event, default=str)}\n\n"


# ------------------------------------------------------------------ review

@router.post("/review")
def review(body: ReviewIn):
    repo = _repo_or_404(body.repo_id)
    final = run_pipeline(repo, diff=body.diff, question="review this pull request")
    return _final_payload(final)


# ----------------------------------------------------------- test generation

@router.post("/tests/generate")
def generate_tests(body: TestGenIn):
    repo = _repo_or_404(body.repo_id)
    final = run_pipeline(repo, question=f"generate tests for {body.target}",
                         target=body.target)
    return _final_payload(final)


# --------------------------------------------------------------------- eval

@router.post("/eval/run")
def run_eval(body: EvalIn):
    from app.evaluator.runner import evaluate
    repo = _repo_or_404(body.repo_id) if body.repo_id else manager().demo_repo()
    report = evaluate(repo, categories=body.categories, limit=body.limit)
    return report


# ------------------------------------------------------------------- health

@router.get("/health")
def health():
    llm = get_llm()
    return {
        "status": "ok",
        "version": "0.1.0",
        "llm": llm.describe(),
        "repos_loaded": len(manager().list_repos()),
    }


def _final_payload(final: dict) -> dict:
    return {
        "answer": final.get("answer", ""),
        "citations": final.get("citations", []),
        "events": final.get("events", []),
        "verification": final.get("verification"),
        "agent_results": final.get("results", {}),
        "duration_ms": final.get("duration_ms"),
        "graph_backend": final.get("graph_backend"),
        "error": final.get("error"),
    }

"""Evaluation runner: executes every dataset question against the real pipeline.

Usage (CLI):
    python -m app.evaluator.runner --repo ../demo-repos/ecommerce-api --out ../eval

Every number in the generated report comes from an actual run.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time

from app.agents.supervisor import run_pipeline
from app.evaluator.dataset import QUESTIONS
from app.evaluator.metrics import (
    aggregate,
    citation_correctness,
    keyword_hit,
    recall_at_k,
    render_markdown,
)
from app.llm import get_llm
from app.repo_manager import RepoManager

log = logging.getLogger("repopilot.eval")


def evaluate(repo, categories: list[str] | None = None, limit: int | None = None) -> dict:
    llm = get_llm()
    rows: list[dict] = []
    questions = [q for q in QUESTIONS if not categories or q["category"] in categories]
    if limit:
        questions = questions[:limit]

    for q in questions:
        t0 = time.time()
        try:
            final = run_pipeline(
                repo, question=q.get("question", ""), diff=q.get("diff", ""),
                target=q.get("target", ""), narrate=False,  # deterministic: no LLM prose
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("question %s failed", q["id"])
            final = {"answer": f"error: {exc}", "citations": [], "results": {},
                     "verification": None}
        latency_ms = round((time.time() - t0) * 1000, 1)

        # retrieval-level recall (deterministic retriever, same query)
        sr = repo.retriever.search(q.get("question", ""), k=10)
        retrieved_files = sr.files
        gold = q.get("expected_files", [])

        cited_files = [c["file"] for c in (final.get("citations") or [])]
        answer = final.get("answer", "") or ""
        results = final.get("results") or {}

        # ---- task success per category
        success = False
        route_ok = bool(results.get(q["task"]))
        if q["category"] == "pr_review":
            findings = (results.get("review") or {}).get("findings", [])
            expected = [f["category"] for f in q.get("expected_findings", [])]
            detected = {f["category"] for f in findings}
            success = route_ok and all(e in detected for e in expected) and \
                keyword_hit(answer, q.get("expect_keywords", []))
            row_extra = {"detected_findings": sorted(detected),
                         "expected_findings": sorted(expected)}
        elif q["category"] == "test_generation":
            v = final.get("verification") or {}
            expected_v = q.get("expect_verification", [])
            success = v.get("status") in expected_v and v.get("total", 0) > 0
            row_extra = {"verification": v.get("status"), "passed": v.get("passed"),
                         "total": v.get("total")}
        else:
            # gold files should appear in citations OR the answer, plus keywords
            gold_in_answer = all(g in answer or g in " ".join(cited_files) for g in gold)
            success = route_ok and keyword_hit(answer, q.get("expect_keywords", [])) and \
                (not gold or gold_in_answer)
            row_extra = {}

        rows.append({
            "id": q["id"], "category": q["category"], "task": q["task"],
            "question": q.get("question", "")[:80],
            "success": success,
            "recall@5": recall_at_k(retrieved_files, gold, 5),
            "recall@10": recall_at_k(retrieved_files, gold, 10),
            "citation_correctness": citation_correctness(cited_files, gold),
            "latency_ms": latency_ms,
            "cited_files": cited_files[:6],
            "retrieved_files": retrieved_files[:10],
            "route_taken": final.get("route"),
            "route_ok": route_ok,
            **row_extra,
        })
        log.info("%s %s success=%s %.0fms", q["id"], q["category"], success, latency_ms)

    summary = aggregate(rows)
    summary["llm_provider"] = llm.describe()
    summary["narration"] = "off — deterministic evaluation (LLM narration disabled)"
    summary["repo"] = repo.repo_id
    return {"summary": summary, "rows": rows}


def write_report(report: dict, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    with open(os.path.join(out_dir, "results.md"), "w", encoding="utf-8") as fh:
        fh.write(render_markdown(report["summary"], report["rows"]) + "\n")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Run the RepoPilot evaluation suite")
    parser.add_argument("--repo", default=None, help="repository source (path or URL)")
    parser.add_argument("--demo", action="store_true", help="evaluate the bundled demo repo")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "..", "eval"))
    parser.add_argument("--categories", nargs="*", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    manager = RepoManager()
    repo = manager.ingest(args.repo) if args.repo else manager.demo_repo()
    report = evaluate(repo, categories=args.categories, limit=args.limit)
    write_report(report, os.path.abspath(args.out))
    s = report["summary"]
    print(json.dumps({k: v for k, v in s.items() if k != "by_category"}, indent=2))
    print(f"\nReport written to {os.path.abspath(args.out)}/results.md")


if __name__ == "__main__":
    main()

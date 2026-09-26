"""Evaluation metrics: retrieval recall, citation correctness, task success, latency."""

from __future__ import annotations

import statistics


def recall_at_k(retrieved_files: list[str], gold_files: list[str], k: int) -> float | None:
    """Fraction of gold files present in the top-k retrieved files."""
    if not gold_files:
        return None
    top = retrieved_files[:k]
    hit = sum(1 for g in gold_files if g in top)
    return hit / len(gold_files)


def citation_correctness(cited_files: list[str], gold_files: list[str]) -> float | None:
    """Share of citations that point at gold (or gold-adjacent) files."""
    if not cited_files or not gold_files:
        return None
    hit = sum(1 for c in cited_files if c in gold_files)
    return hit / len(cited_files)


def keyword_hit(answer: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    low = (answer or "").lower()
    return any(kw.lower() in low for kw in keywords)


def p50(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(0.95 * (len(ordered) - 1))))
    return ordered[idx]


def aggregate(rows: list[dict]) -> dict:
    """Aggregate per-question rows into a summary report."""
    out: dict = {"questions": len(rows), "by_category": {}}
    recalls5, recalls10, cites, lats, successes = [], [], [], [], []
    cat_rows: dict[str, list[dict]] = {}
    for r in rows:
        cat_rows.setdefault(r["category"], []).append(r)
        if r.get("recall@5") is not None:
            recalls5.append(r["recall@5"])
        if r.get("recall@10") is not None:
            recalls10.append(r["recall@10"])
        if r.get("citation_correctness") is not None:
            cites.append(r["citation_correctness"])
        lats.append(r.get("latency_ms", 0))
        successes.append(1.0 if r.get("success") else 0.0)
    out["retrieval_recall@5"] = round(sum(recalls5) / len(recalls5), 3) if recalls5 else None
    out["retrieval_recall@10"] = round(sum(recalls10) / len(recalls10), 3) if recalls10 else None
    out["citation_correctness"] = round(sum(cites) / len(cites), 3) if cites else None
    out["task_success_rate"] = round(sum(successes) / len(successes), 3) if rows else None
    out["latency_ms_p50"] = round(p50(lats), 1)
    out["latency_ms_p95"] = round(p95(lats), 1)
    for cat, rs in cat_rows.items():
        out["by_category"][cat] = {
            "questions": len(rs),
            "task_success": round(sum(1 for r in rs if r.get("success")) / len(rs), 3),
            "recall@5": round(
                sum(r["recall@5"] for r in rs if r.get("recall@5") is not None) /
                max(1, sum(1 for r in rs if r.get("recall@5") is not None)), 3)
            if any(r.get("recall@5") is not None for r in rs) else None,
        }
    return out


def render_markdown(summary: dict, rows: list[dict]) -> str:
    lines = [
        "# RepoPilot Evaluation Report", "",
        f"Questions: **{summary['questions']}**",
        f"Retrieval Recall@5: **{summary['retrieval_recall@5']}**",
        f"Retrieval Recall@10: **{summary['retrieval_recall@10']}**",
        f"Citation correctness: **{summary['citation_correctness']}**",
        f"Agent task success: **{summary['task_success_rate']}**",
        f"Latency p50 / p95: **{summary['latency_ms_p50']} ms / {summary['latency_ms_p95']} ms**",
        "",
        "| Category | Questions | Task success | Recall@5 |",
        "|---|---|---|---|",
    ]
    for cat, m in summary["by_category"].items():
        lines.append(f"| {cat} | {m['questions']} | {m['task_success']} | {m['recall@5']} |")
    lines += ["", "## Per-question results", "",
              "| id | category | success | recall@5 | latency (ms) |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['id']} | {r['category']} | {'✅' if r.get('success') else '❌'} | "
            f"{r.get('recall@5')} | {r.get('latency_ms')} |")
    return "\n".join(lines)

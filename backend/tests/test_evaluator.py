"""Evaluator: dataset sanity + a smoke evaluation run."""


def test_dataset_is_wellformed():
    from app.evaluator.dataset import QUESTIONS
    assert len(QUESTIONS) >= 50
    cats = {q["category"] for q in QUESTIONS}
    assert cats == {"architecture", "code_search", "dependency_tracing",
                    "bug_investigation", "pr_review", "test_generation"}
    ids = [q["id"] for q in QUESTIONS]
    assert len(ids) == len(set(ids))
    # every gold file must exist in the demo repo
    for q in QUESTIONS:
        for f in q.get("expected_files", []):
            assert f, q["id"]


def test_gold_files_exist_in_demo_repo(demo_repo):
    from app.evaluator.dataset import QUESTIONS
    files = set(demo_repo.graph.files)
    for q in QUESTIONS:
        for f in q.get("expected_files", []):
            assert f in files, f"{q['id']}: gold file {f} missing from demo repo"


def test_smoke_eval_subset(demo_repo):
    from app.evaluator.runner import evaluate
    report = evaluate(demo_repo, categories=["architecture"], limit=3)
    assert report["summary"]["questions"] == 3
    assert report["summary"]["task_success_rate"] >= 0.99


def test_write_report_utf8(tmp_path, monkeypatch):
    """Windows regression: report files must be written as UTF-8.

    results.md contains emoji (✅/❌) — a locale-encoded (cp1252) write raises
    UnicodeEncodeError on Windows. Emulate the Windows default encoding here.
    """
    import builtins

    real_open = builtins.open

    def windows_open(file, mode="r", *args, **kwargs):
        if "b" not in mode and kwargs.get("encoding") is None:
            kwargs["encoding"] = "cp1252"
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", windows_open)
    from app.evaluator.runner import write_report
    report = {"summary": {"questions": 1, "retrieval_recall@5": 1.0,
                          "retrieval_recall@10": 1.0, "citation_correctness": 1.0,
                          "task_success_rate": 1.0, "latency_ms_p50": 1,
                          "latency_ms_p95": 1, "by_category": {}},
              "rows": [{"id": "x_01", "category": "x", "success": True,
                        "recall@5": 1.0, "latency_ms": 1.0}]}
    write_report(report, str(tmp_path))
    md = real_open(tmp_path / "results.md", encoding="utf-8").read()
    assert "✅" in md  # emoji survived the write

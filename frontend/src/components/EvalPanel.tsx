"use client";

import { useState } from "react";
import { api, EvalReport, RepoOverview } from "@/lib/api";

function Metric({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-xl border border-surface-700/60 bg-surface-900/60 p-4">
      <div className="text-2xl font-bold text-white">{value}</div>
      <div className="text-[12px] text-slate-400 mt-1">{label}</div>
      {hint && <div className="text-[11px] text-slate-600 mt-0.5">{hint}</div>}
    </div>
  );
}

export default function EvalPanel({ repo }: { repo: RepoOverview | null }) {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    if (!repo) return;
    setBusy(true);
    setError("");
    try {
      setReport(await api.runEval(repo.repo_id));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const s = report?.summary;

  return (
    <div className="h-full overflow-y-auto px-6 py-5">
      <div className="max-w-3xl mx-auto space-y-4">
        <h2 className="text-lg font-semibold text-white">Evaluation</h2>
        <p className="text-[13px] text-slate-400 leading-relaxed">
          Runs the 56-question dataset (architecture / code search / dependency
          tracing / bug investigation / PR review / test generation) against the
          live pipeline and measures retrieval recall, citation correctness, task
          success and latency. Every number comes from a real run.
        </p>
        <button
          onClick={run}
          disabled={busy || !repo}
          className="px-5 py-2.5 rounded-xl bg-indigo-500/90 hover:bg-indigo-400 disabled:opacity-40 text-white text-sm font-semibold transition"
        >
          {busy ? "Running evaluation…" : "Run evaluation suite"}
        </button>
        {error && <div className="text-rose-400 text-sm">{error}</div>}

        {s && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Metric label="Task success" value={fmt(s.task_success_rate)} />
              <Metric label="Retrieval Recall@5" value={fmt(s["retrieval_recall@5"])} />
              <Metric label="Recall@10" value={fmt(s["retrieval_recall@10"])} />
              <Metric
                label="Latency p50 / p95"
                value={`${s.latency_ms_p50} / ${s.latency_ms_p95}ms`}
                hint={`LLM: ${s.llm_provider.provider}`}
              />
            </div>

            <div className="rounded-xl border border-surface-700/60 overflow-hidden">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="bg-surface-800/80 text-slate-400 text-left">
                    <th className="px-4 py-2 font-medium">Category</th>
                    <th className="px-4 py-2 font-medium">Questions</th>
                    <th className="px-4 py-2 font-medium">Task success</th>
                    <th className="px-4 py-2 font-medium">Recall@5</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(s.by_category).map(([cat, m]) => (
                    <tr key={cat} className="border-t border-surface-700/40">
                      <td className="px-4 py-2 text-slate-200">{cat}</td>
                      <td className="px-4 py-2 text-slate-400">{m.questions}</td>
                      <td className="px-4 py-2 text-emerald-300">{fmt(m.task_success)}</td>
                      <td className="px-4 py-2 text-slate-400">{fmt(m["recall@5"])}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <details>
              <summary className="text-[13px] text-slate-400 cursor-pointer hover:text-slate-200">
                per-question results ({report!.rows.length})
              </summary>
              <div className="mt-2 rounded-xl border border-surface-700/60 overflow-hidden max-h-80 overflow-y-auto">
                <table className="w-full text-[12.5px]">
                  <tbody>
                    {report!.rows.map((r) => (
                      <tr key={r.id} className="border-t border-surface-700/40">
                        <td className="px-3 py-1.5 font-mono text-slate-400">{r.id}</td>
                        <td className="px-3 py-1.5 text-slate-500">{r.category}</td>
                        <td className="px-3 py-1.5">{r.success ? "✅" : "❌"}</td>
                        <td className="px-3 py-1.5 text-slate-500">
                          r@5 {r["recall@5"] ?? "—"}
                        </td>
                        <td className="px-3 py-1.5 text-slate-600 text-right">
                          {r.latency_ms}ms
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${Math.round(v * 100)}%`;
}

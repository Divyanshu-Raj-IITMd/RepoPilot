"use client";

import { useState } from "react";
import { api, ChatResponse, RepoOverview } from "@/lib/api";
import { FindingsTable, TraceView } from "./TraceView";

const SAMPLE_DIFF = `diff --git a/app/services/orders.py b/app/services/orders.py
--- a/app/services/orders.py
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
`;

export default function ReviewPanel({ repo }: { repo: RepoOverview | null }) {
  const [diff, setDiff] = useState("");
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run() {
    if (!repo || !diff.trim()) return;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.review(repo.repo_id, diff));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!repo) {
    return (
      <div className="h-full grid place-items-center text-slate-400 text-sm">
        Load a repository first.
      </div>
    );
  }

  const findings = result?.agent_results?.review?.findings ?? [];

  return (
    <div className="h-full overflow-y-auto px-6 py-5">
      <div className="max-w-3xl mx-auto space-y-4">
        <h2 className="text-lg font-semibold text-white">PR Review Agent</h2>
        <p className="text-[13px] text-slate-400">
          Paste a unified diff. Deterministic checks run over the changed lines —
          correctness, security, performance, maintainability, tests and breaking
          changes — with the repository as context.
        </p>
        <textarea
          value={diff}
          onChange={(e) => setDiff(e.target.value)}
          rows={12}
          spellCheck={false}
          placeholder="Paste a unified diff (git diff)…"
          className="w-full bg-surface-950/80 border border-surface-700/60 rounded-xl p-3 font-mono text-[12px] outline-none focus:border-indigo-500/50"
        />
        <div className="flex gap-3">
          <button
            onClick={run}
            disabled={busy || !diff.trim()}
            className="px-5 py-2.5 rounded-xl bg-indigo-500/90 hover:bg-indigo-400 disabled:opacity-40 text-white text-sm font-semibold transition"
          >
            {busy ? "Reviewing…" : "Review diff"}
          </button>
          <button
            onClick={() => setDiff(SAMPLE_DIFF.trim())}
            className="px-4 py-2.5 rounded-xl border border-surface-700/60 text-slate-300 hover:border-indigo-500/40 text-sm transition"
          >
            Use seeded sample
          </button>
        </div>
        {error && <div className="text-rose-400 text-sm">{error}</div>}

        {result && (
          <div className="space-y-3">
            <div className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-slate-200">
              {result.answer}
            </div>
            <FindingsTable findings={findings} />
            <TraceView events={result.events} />
          </div>
        )}
      </div>
    </div>
  );
}

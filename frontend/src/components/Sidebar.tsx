"use client";

import { useEffect, useState } from "react";
import { api, Health, RepoOverview } from "@/lib/api";

const TABS = [
  { id: "chat", label: "Chat", icon: "💬" },
  { id: "review", label: "PR Review", icon: "🔍" },
  { id: "tests", label: "Test Gen", icon: "🧪" },
  { id: "eval", label: "Evaluation", icon: "📊" },
] as const;

export type TabId = (typeof TABS)[number]["id"];

export default function Sidebar({
  tab,
  onTab,
  repo,
  onRepoChange,
}: {
  tab: TabId;
  onTab: (t: TabId) => void;
  repo: RepoOverview | null;
  onRepoChange: (r: RepoOverview | null) => void;
}) {
  const [health, setHealth] = useState<Health | null>(null);
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, [repo]);

  async function loadDemo() {
    setBusy(true);
    setError("");
    try {
      onRepoChange(await api.addDemoRepo());
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function addRepo() {
    if (!source.trim()) return;
    setBusy(true);
    setError("");
    try {
      onRepoChange(await api.addRepo(source.trim()));
      setSource("");
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="w-72 shrink-0 h-full flex flex-col border-r border-surface-700/60 bg-surface-900/60">
      <div className="p-5 border-b border-surface-700/60">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-emerald-400 grid place-items-center text-lg font-black text-surface-950">
            R
          </div>
          <div>
            <div className="font-bold tracking-tight text-white">RepoPilot</div>
            <div className="text-[11px] text-slate-400 -mt-0.5">
              agentic code intelligence
            </div>
          </div>
        </div>
      </div>

      <nav className="p-3 space-y-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => onTab(t.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition ${
              tab === t.id
                ? "bg-indigo-500/15 text-indigo-300 border border-indigo-500/30"
                : "text-slate-400 hover:bg-surface-800 hover:text-slate-200 border border-transparent"
            }`}
          >
            <span>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </nav>

      <div className="px-3 py-4 border-t border-surface-700/60 overflow-y-auto">
        <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-2 px-1">
          Repository
        </div>
        {repo ? (
          <div className="rounded-lg border border-surface-700/60 bg-surface-800/50 p-3 text-xs space-y-2">
            <div className="font-semibold text-slate-100">{repo.name}</div>
            <div className="flex flex-wrap gap-1">
              {repo.frameworks.map((f) => (
                <span key={f} className="px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300">
                  {f}
                </span>
              ))}
              {repo.databases.map((d) => (
                <span key={d} className="px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-300">
                  {d}
                </span>
              ))}
            </div>
            <div className="text-slate-400">
              {repo.file_count} files · {repo.loc.toLocaleString()} loc ·{" "}
              {repo.symbols} symbols · {repo.endpoints.length} endpoints
            </div>
            {repo.security_findings.length > 0 && (
              <div className="text-amber-300">
                ⚠ {repo.security_findings.length} secret-scan finding(s) ·{" "}
                {repo.security_findings[0].file}
              </div>
            )}
            <button
              onClick={() => onRepoChange(null)}
              className="text-[11px] text-slate-500 hover:text-slate-300 underline"
            >
              switch repository
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <input
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="git URL or local path"
              className="w-full bg-surface-950/80 border border-surface-700/60 rounded-lg px-3 py-2 text-xs outline-none focus:border-indigo-500/50"
              onKeyDown={(e) => e.key === "Enter" && addRepo()}
            />
            <button
              onClick={addRepo}
              disabled={busy || !source.trim()}
              className="w-full py-2 rounded-lg bg-indigo-500/90 hover:bg-indigo-400 disabled:opacity-40 text-white text-xs font-semibold transition"
            >
              {busy ? "Indexing…" : "Add repository"}
            </button>
            <button
              onClick={loadDemo}
              disabled={busy}
              className="w-full py-2 rounded-lg border border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 text-xs font-semibold transition disabled:opacity-40"
            >
              {busy ? "Indexing…" : "Load bundled demo repo"}
            </button>
            {error && <div className="text-[11px] text-rose-400">{error}</div>}
            <p className="text-[11px] text-slate-500 leading-relaxed px-1 pt-1">
              Clones, parses (AST), builds the code graph and semantic index, and
              runs the secret scanner.
            </p>
          </div>
        )}
      </div>

      <div className="mt-auto p-4 border-t border-surface-700/60 text-[11px] text-slate-500">
        {health && (
          <>
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  health.llm.available ? "bg-emerald-400" : "bg-amber-400"
                }`}
              />
              LLM: <span className="text-slate-300">{health.llm.provider}</span>
              {health.llm.model ? ` (${health.llm.model})` : ""}
            </div>
            <div className="mt-1">
              {health.llm.available
                ? health.llm.remote
                  ? "remote free-tier API"
                  : "local model (Ollama)"
                : "offline heuristic mode — structured findings are deterministic"}
            </div>
          </>
        )}
      </div>
    </aside>
  );
}

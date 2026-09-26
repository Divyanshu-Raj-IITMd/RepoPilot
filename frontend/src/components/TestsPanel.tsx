"use client";

import { useEffect, useState } from "react";
import { api, ChatResponse, RepoOverview } from "@/lib/api";
import { VerificationCard } from "./TraceView";

export default function TestsPanel({ repo }: { repo: RepoOverview | null }) {
  const [target, setTarget] = useState("");
  const [symbols, setSymbols] = useState<string[]>([]);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!repo) return;
    // cheap symbol hint list from the overview endpoints + common demo targets
    const hints = Array.from(
      new Set([
        ...(repo.endpoints?.map((e) => e.handler) ?? []),
        "calculate_invoice",
        "encode_token",
        "decode_token",
        "list_orders",
        "create_user",
      ]),
    );
    setSymbols(hints);
  }, [repo]);

  async function run(t?: string) {
    const tgt = (t ?? target).trim();
    if (!repo || !tgt) return;
    setTarget(tgt);
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(await api.generateTests(repo.repo_id, tgt));
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

  return (
    <div className="h-full overflow-y-auto px-6 py-5">
      <div className="max-w-3xl mx-auto space-y-4">
        <h2 className="text-lg font-semibold text-white">
          Test Generation + Verification Loop
        </h2>
        <p className="text-[13px] text-slate-400 leading-relaxed">
          The agent analyses the target&apos;s signature (AST), derives a category
          matrix — normal / empty / zero / negative / large / boundary / invalid —
          renders a pytest module, and <span className="text-emerald-300">runs it in a sandboxed executor</span>.
          Failures are classified, a validation patch may be proposed and re-run:
          nothing is reported as &quot;working&quot; until the tests actually pass.
        </p>

        <div className="flex gap-3">
          <input
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder="function name, e.g. calculate_invoice"
            list="symbol-hints"
            className="flex-1 bg-surface-950/80 border border-surface-700/60 rounded-xl px-4 py-2.5 font-mono text-sm outline-none focus:border-indigo-500/50"
          />
          <datalist id="symbol-hints">
            {symbols.map((s) => (
              <option key={s} value={s} />
            ))}
          </datalist>
          <button
            onClick={() => run()}
            disabled={busy || !target.trim()}
            className="px-5 py-2.5 rounded-xl bg-indigo-500/90 hover:bg-indigo-400 disabled:opacity-40 text-white text-sm font-semibold transition"
          >
            {busy ? "Generating…" : "Generate & verify"}
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {["calculate_invoice", "encode_token", "decode_token"].map((s) => (
            <button
              key={s}
              onClick={() => run(s)}
              className="px-3 py-1.5 rounded-lg border border-surface-700/60 font-mono text-[12px] text-slate-300 hover:border-indigo-500/40 hover:text-white transition"
            >
              {s}
            </button>
          ))}
        </div>

        {error && <div className="text-rose-400 text-sm">{error}</div>}
        {busy && (
          <div className="text-slate-500 text-sm animate-pulse">
            deriving cases → writing pytest module → sandboxed run → classifying
            failures…
          </div>
        )}

        {result?.verification && <VerificationCard v={result.verification} />}
      </div>
    </div>
  );
}

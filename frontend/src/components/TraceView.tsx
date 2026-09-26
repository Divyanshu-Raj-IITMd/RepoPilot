"use client";

import { useState } from "react";
import { Citation, Finding, TraceEvent, Verification } from "@/lib/api";

export function TraceView({ events }: { events: TraceEvent[] }) {
  if (!events.length) return null;
  return (
    <div className="mt-3 rounded-lg border border-surface-700/60 bg-surface-950/50 p-3">
      <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-2">
        Agent trace
      </div>
      <ol className="space-y-1.5">
        {events.map((e, i) => (
          <li key={i} className="flex gap-2.5 items-start text-[12px]">
            <span className="text-slate-600 font-mono shrink-0 w-5 text-right">
              {i + 1}
            </span>
            <span
              className={`shrink-0 mt-0.5 w-1.5 h-1.5 rounded-full ${
                e.step === "supervisor"
                  ? "bg-indigo-400"
                  : e.step === "verification"
                    ? "bg-emerald-400"
                    : "bg-sky-400"
              }`}
            />
            <span className="text-slate-300">
              {e.step === "supervisor" ? (
                <>
                  supervisor <span className="text-indigo-300">→ {e.route}</span>{" "}
                  <span className="text-slate-500">{e.reason}</span>
                </>
              ) : e.step === "agent" ? (
                <>
                  agent <span className="text-sky-300">{e.agent}</span>{" "}
                  <span className="text-slate-500">{e.status}</span>
                  {typeof e.findings === "number" && (
                    <span className="text-slate-500"> · {e.findings} findings</span>
                  )}
                  {typeof e.passed === "number" && typeof e.total === "number" && (
                    <span className="text-emerald-300">
                      {" "}
                      · {e.passed}/{e.total} tests
                    </span>
                  )}
                </>
              ) : e.step === "tool" ? (
                <>
                  tool <span className="text-amber-300">{e.tool}</span>{" "}
                  <span className="text-slate-500">{e.iteration ? `iter ${e.iteration}` : ""}</span>
                </>
              ) : (
                <>{e.step}</>
              )}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function Citations({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!citations.length) return null;
  return (
    <div className="mt-3">
      <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-2">
        Evidence ({citations.length})
      </div>
      <div className="flex flex-wrap gap-1.5">
        {citations.map((c, i) => {
          const key = `${c.file}:${c.start_line}`;
          return (
            <button
              key={i}
              onClick={() => setOpen(open === key ? null : key)}
              className="px-2 py-1 rounded-md text-[11.5px] font-mono border border-surface-700/60 bg-surface-800/60 text-slate-300 hover:border-indigo-500/50 hover:text-indigo-300 transition"
            >
              {c.file}:{c.start_line}
              {c.symbol ? <span className="text-slate-500"> · {c.symbol}</span> : null}
            </button>
          );
        })}
      </div>
      {open && (
        <div className="mt-2 rounded-lg border border-surface-700/60 overflow-hidden">
          {citations
            .filter((c) => `${c.file}:${c.start_line}` === open)
            .map((c, i) => (
              <div key={i}>
                <div className="px-3 py-1.5 bg-surface-800/80 text-[11px] text-slate-400 flex justify-between">
                  <span className="font-mono">
                    {c.file}:{c.start_line}–{c.end_line}
                  </span>
                  <span>{c.reason}</span>
                </div>
                <pre className="codeblock !rounded-none border-0">{c.snippet}</pre>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

const SEV_STYLE: Record<string, string> = {
  HIGH: "bg-rose-500/15 text-rose-300 border-rose-500/30",
  MEDIUM: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  LOW: "bg-sky-500/15 text-sky-300 border-sky-500/30",
};

export function FindingsTable({ findings }: { findings: Finding[] }) {
  if (!findings.length) return null;
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-surface-700/60">
      <table className="w-full text-[12.5px]">
        <thead>
          <tr className="bg-surface-800/80 text-slate-400 text-left">
            <th className="px-3 py-2 font-medium">Severity</th>
            <th className="px-3 py-2 font-medium">Finding</th>
            <th className="px-3 py-2 font-medium">Location</th>
          </tr>
        </thead>
        <tbody>
          {findings.map((f, i) => (
            <tr key={i} className="border-t border-surface-700/40 hover:bg-surface-800/40">
              <td className="px-3 py-2">
                <span
                  className={`px-2 py-0.5 rounded border text-[11px] font-semibold ${
                    SEV_STYLE[f.severity]
                  }`}
                >
                  {f.severity}
                </span>
              </td>
              <td className="px-3 py-2">
                <div className="text-slate-200">{f.title}</div>
                <div className="text-[11.5px] text-slate-500">{f.rationale}</div>
              </td>
              <td className="px-3 py-2 font-mono text-[11.5px] text-slate-400 whitespace-nowrap">
                {f.file}:{f.line}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function VerificationCard({ v }: { v: Verification }) {
  const ok = v.status === "validated" || v.status === "validated_after_fix";
  return (
    <div
      className={`mt-3 rounded-lg border p-4 ${
        ok
          ? "border-emerald-500/30 bg-emerald-500/5"
          : "border-rose-500/30 bg-rose-500/5"
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="font-semibold">
          {ok ? "✅" : "⛔"} Verification loop —{" "}
          <span className={ok ? "text-emerald-300" : "text-rose-300"}>{v.status}</span>
        </div>
        <div className="font-mono text-sm">
          {v.passed}/{v.total} tests passed
        </div>
      </div>
      <div className="mt-2 text-[12.5px] text-slate-400">
        {v.iterations.length} iteration(s):{" "}
        {v.iterations
          .map((it) => `${it.passed}/${it.passed + it.failed + it.errors} (${it.executor})`)
          .join(" → ")}
      </div>
      {v.patch && (
        <div className="mt-3">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
            Proposed patch — {v.patch.description}
          </div>
          <pre className="codeblock !text-emerald-200">{v.patch.code}</pre>
        </div>
      )}
      {v.test_code && (
        <details className="mt-3">
          <summary className="text-[12.5px] text-slate-400 cursor-pointer hover:text-slate-200">
            show generated test file ({v.test_file})
          </summary>
          <pre className="codeblock mt-2">{v.test_code}</pre>
        </details>
      )}
    </div>
  );
}

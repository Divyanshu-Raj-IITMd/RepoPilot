"use client";

import { useEffect, useRef, useState } from "react";
import { api, chatStream, ChatResponse, RepoOverview, TraceEvent } from "@/lib/api";
import { Citations, TraceView, VerificationCard } from "./TraceView";

interface Msg {
  role: "user" | "assistant";
  text?: string;
  resp?: ChatResponse;
  liveTrace?: TraceEvent[];
}

const SUGGESTIONS = [
  "Why might GET /api/users/{username} return HTTP 500?",
  "Where is JWT authentication implemented?",
  "Which files import app/services/users?",
  "What is the architecture of this repository?",
  "generate tests for calculate_invoice",
];

export default function ChatPanel({ repo }: { repo: RepoOverview | null }) {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function send(text: string) {
    if (!repo || !text.trim() || busy) return;
    setInput("");
    setBusy(true);
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", liveTrace: [] }]);
    try {
      const final = await chatStream(repo.repo_id, text, (e) => {
        setMessages((m) => {
          const last = m[m.length - 1];
          if (last.role !== "assistant") return m;
          return [...m.slice(0, -1), { ...last, liveTrace: [...(last.liveTrace ?? []), e] }];
        });
      });
      setMessages((m) => [...m.slice(0, -1), { role: "assistant", resp: final }]);
    } catch (e) {
      setMessages((m) => [
        ...m.slice(0, -1),
        { role: "assistant", text: `⚠ ${String(e)}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  if (!repo) {
    return (
      <Center>
        <h2 className="text-xl font-semibold text-white">Load a repository to start</h2>
        <p className="text-slate-400 mt-2 max-w-md text-sm leading-relaxed">
          RepoPilot will clone it, parse every file with an AST, build the
          dependency graph, embed a semantic index and scan for exposed secrets —
          then five specialist agents answer your questions with file:line
          evidence.
        </p>
      </Center>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {messages.length === 0 && (
          <div className="max-w-2xl mx-auto pt-8">
            <h2 className="text-lg font-semibold text-white">
              Ask about <span className="text-indigo-300">{repo.name}</span>
            </h2>
            <div className="mt-4 grid gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="text-left px-4 py-2.5 rounded-lg border border-surface-700/60 bg-surface-900/60 text-[13px] text-slate-300 hover:border-indigo-500/40 hover:text-white transition"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) =>
          m.role === "user" ? (
            <div key={i} className="flex justify-end">
              <div className="max-w-[75%] rounded-2xl rounded-br-sm bg-indigo-500/90 text-white px-4 py-2.5 text-[13.5px]">
                {m.text}
              </div>
            </div>
          ) : (
            <div key={i} className="max-w-[88%]">
              {m.resp ? (
                <>
                  <div className="whitespace-pre-wrap text-[13.5px] leading-relaxed text-slate-200">
                    {m.resp.answer}
                  </div>
                  {m.resp.verification && <VerificationCard v={m.resp.verification} />}
                  {m.resp.citations.length > 0 && <Citations citations={m.resp.citations} />}
                  <TraceView events={m.resp.events} />
                  <div className="mt-2 text-[11px] text-slate-600">
                    {m.resp.graph_backend} · {m.resp.duration_ms?.toLocaleString()} ms
                    {m.resp.citations.length > 0 &&
                      ` · ${m.resp.citations.length} citations`}
                  </div>
                </>
              ) : (
                <div>
                  <div className="text-slate-500 text-[13px] animate-pulse">
                    agents working…
                  </div>
                  <TraceView events={m.liveTrace ?? []} />
                </div>
              )}
            </div>
          ),
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-surface-700/60 p-4">
        <div className="flex gap-3 max-w-3xl mx-auto">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
            placeholder="Ask anything about the repository…"
            disabled={busy}
            className="flex-1 bg-surface-900/80 border border-surface-700/60 rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-500/50 disabled:opacity-50"
          />
          <button
            onClick={() => send(input)}
            disabled={busy || !input.trim()}
            className="px-5 rounded-xl bg-indigo-500/90 hover:bg-indigo-400 disabled:opacity-40 text-white text-sm font-semibold transition"
          >
            {busy ? "…" : "Ask"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return (
    <div className="h-full grid place-items-center text-center px-6">
      <div>{children}</div>
    </div>
  );
}

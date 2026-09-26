// RepoPilot API client — types + fetch helpers + SSE stream reader.

export interface Citation {
  file: string;
  start_line: number;
  end_line: number;
  snippet: string;
  reason: string;
  symbol?: string | null;
}

export interface Finding {
  severity: "HIGH" | "MEDIUM" | "LOW";
  category: string;
  title: string;
  file: string;
  line: number;
  snippet: string;
  rationale: string;
}

export interface TraceEvent {
  step: string;
  ts: number;
  agent?: string;
  status?: string;
  action?: string;
  route?: string;
  reason?: string;
  tool?: string;
  iteration?: number;
  passed?: number;
  failed?: number;
  total?: number;
  findings?: number;
  hypotheses?: number;
  files?: number;
  tests?: number;
  patch?: string;
  [k: string]: unknown;
}

export interface Verification {
  status: "validated" | "validated_after_fix" | "rejected" | "error";
  target: string;
  total: number;
  passed: number;
  iterations: {
    iteration: number;
    passed: number;
    failed: number;
    errors: number;
    failed_tests: string[];
    failure_classes: Record<string, string[]>;
    output_tail: string;
    executor: string;
    duration_s: number;
  }[];
  patch?: { target: string; description: string; code: string } | null;
  summary: string;
  test_file: string;
  test_code: string;
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  events: TraceEvent[];
  verification: Verification | null;
  agent_results: Record<string, { summary: string; findings: Finding[]; narrative?: string }>;
  duration_ms: number;
  graph_backend: string;
  error?: string | null;
}

export interface RepoOverview {
  repo_id: string;
  name: string;
  source: string;
  languages: Record<string, number>;
  frameworks: string[];
  databases: string[];
  entry_points: string[];
  dir_roles: Record<string, string[]>;
  file_count: number;
  loc: number;
  test_files: string[];
  endpoints: { method: string; path: string; handler: string; file: string; line: number }[];
  security_findings: { kind: string; title: string; file: string; line: number; match: string }[];
  symbols: number;
}

export interface Health {
  status: string;
  version: string;
  llm: { provider: string; available: boolean; remote: boolean; model: string | null };
  repos_loaded: number;
}

export interface EvalReport {
  summary: {
    questions: number;
    "retrieval_recall@5": number | null;
    "retrieval_recall@10": number | null;
    citation_correctness: number | null;
    task_success_rate: number | null;
    latency_ms_p50: number;
    latency_ms_p95: number;
    llm_provider: { provider: string; available: boolean };
    by_category: Record<string, { questions: number; task_success: number; "recall@5": number | null }>;
  };
  rows: {
    id: string;
    category: string;
    success: boolean;
    "recall@5": number | null;
    latency_ms: number;
  }[];
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch("/api/health").then(json<Health>),
  addRepo: (source: string, name?: string) =>
    fetch("/api/repos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, name }),
    }).then(json<RepoOverview>),
  addDemoRepo: () =>
    fetch("/api/repos/demo", { method: "POST" }).then(json<RepoOverview>),
  listRepos: () => fetch("/api/repos").then(json<{ repos: unknown[] }>),
  chat: (repoId: string, message: string, target?: string) =>
    fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, message, target }),
    }).then(json<ChatResponse>),
  review: (repoId: string, diff: string) =>
    fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, diff }),
    }).then(json<ChatResponse>),
  generateTests: (repoId: string, target: string) =>
    fetch("/api/tests/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId, target }),
    }).then(json<ChatResponse>),
  runEval: (repoId: string) =>
    fetch("/api/eval/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ repo_id: repoId }),
    }).then(json<EvalReport>),
};

/** POST + Server-Sent-Events reader for /api/chat/stream. */
export async function chatStream(
  repoId: string,
  message: string,
  onTrace: (e: TraceEvent) => void,
  target?: string,
): Promise<ChatResponse> {
  const res = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ repo_id: repoId, message, target }),
  });
  if (!res.ok || !res.body) throw new Error("stream failed");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let final: ChatResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      try {
        const payload = JSON.parse(line.slice(6));
        if (payload.event === "trace") onTrace(payload.data as TraceEvent);
        else if (payload.event === "final") final = payload.data as ChatResponse;
        else if (payload.event === "error") throw new Error(payload.data);
      } catch {
        /* ignore malformed keepalives */
      }
    }
  }
  if (!final) throw new Error("stream ended without a final payload");
  return final;
}

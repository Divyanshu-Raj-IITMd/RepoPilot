"""Agent 3 — Issue Investigation Agent.

Investigates "why might X fail?" questions:
  find endpoint -> find controller -> find service -> find DB call ->
  find related models -> find tests -> run static risk checks ->
  generate ranked hypotheses, each citing file:line evidence.
"""

from __future__ import annotations

import re

from app.agents import patterns
from app.agents.findings import AgentResult, Citation, Finding, make_citation
from app.agents.state import EventTap
from app.llm import narrate_or_none

_PATH_RE = re.compile(r"(/[A-Za-z0-9_\-./{}]+)")
_STATUS_RE = re.compile(r"\b(?:HTTP\s*)?(5\d\d|4\d\d)\b")


def investigate(repo, question: str) -> AgentResult:
    EventTap.emit("agent", agent="issue_investigator", status="started", question=question)
    g = repo.graph
    paths = _PATH_RE.findall(question)
    status = _STATUS_RE.search(question)
    status = status.group(1) if status else None
    method_m = re.search(r"\b(GET|POST|PUT|DELETE|PATCH)\b", question, re.I)
    method = method_m.group(1).upper() if method_m else None

    trace = None
    if paths:
        trace = g.trace_route(paths[0], method=method)
        EventTap.emit("tool", agent="issue_investigator", tool="trace_route",
                      path=paths[0], found=bool(trace["route"]))

    citations: list[Citation] = []
    chain_files: list[str] = []
    hypotheses: list[Finding] = []

    if trace and trace["route"]:
        chain_files = trace["files"]
        # cite every hop of the call chain
        for hop in trace["chain"][:8]:
            citations.append(make_citation(
                g, hop["file"], hop["line"], hop["line"] + 2,
                reason=f"call-chain depth {hop['depth']}: {hop['symbol']}",
                symbol=hop["symbol"],
            ))
        if status == "500" or status is None:
            hypotheses.extend(patterns.find_none_deref(g, chain_files))
            hypotheses.extend(patterns.find_missing_error_handling(g, chain_files))
        hypotheses.extend(patterns.find_sql_injection(g, chain_files))
        hypotheses.extend(patterns.find_swallowed_errors(g, chain_files))
        hypotheses.extend(patterns.find_n_plus_one(g, chain_files))
        hypotheses.extend(patterns.find_unvalidated_rates(g, chain_files))
        hypotheses.extend(patterns.find_missing_input_validation(g, chain_files))
        hypotheses.extend(patterns.find_dead_stores(g, chain_files))
        # where else does the traced path appear? (allowlists, middleware, docs)
        route_path = trace["route"].path
        for file, sf in g.files.items():
            if file == trace["route"].file:
                continue
            for ln, line_txt in enumerate(sf.content.splitlines(), 1):
                if f'"{route_path}"' in line_txt or f"'{route_path}'" in line_txt:
                    hypotheses.append(Finding(
                        severity="LOW", category="path_reference",
                        title=f"`{route_path}` is referenced in {file}",
                        file=file, line=ln, snippet=line_txt.strip()[:160],
                        rationale=f"The traced endpoint path also appears in {file} — e.g. "
                                  f"listed in a public-paths allowlist such as PUBLIC_PATHS, "
                                  f"so the middleware may deliberately skip bearer-token "
                                  f"verification for it. Confirm the exemption is intended.",
                    ))
                    break
    else:
        # no route in the question: investigate the most relevant files
        sr = repo.retriever.search(question, k=6)
        chain_files = sr.files[:5]
        for hit in sr.hits[:5]:
            cite = hit.citation()
            citations.append(Citation(file=cite["file"], start_line=cite["start_line"],
                                      end_line=cite["end_line"], snippet=cite["snippet"],
                                      reason=cite["reason"], symbol=cite.get("symbol")))
        hypotheses.extend(patterns.run_all_checks(g, chain_files))
        # security questions surface the ingest-time secret scan
        if re.search(r"secret|credential|password|\bkey\b|\.env|aws|token leak", question, re.I):
            for f in repo.security.findings[:4]:
                hypotheses.append(Finding(
                    severity="HIGH", category="exposed_secret",
                    title=f"{f.title} ({f.kind})", file=f.file, line=f.line,
                    snippet=f.match, rationale="Detected by RepoPilot's secret scanner at "
                    "ingest time; secrets must move to environment variables or a secret "
                    "manager.",
                ))

    # tests touching the involved files
    tests = g.tests_for_files(chain_files) if chain_files else []

    # dedupe hypotheses by (category, file, line)
    seen: set[tuple] = set()
    uniq: list[Finding] = []
    for f in hypotheses:
        key = (f.category, f.file, f.line)
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    severity = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    # question-relevance: within a severity band, findings whose title/rationale/
    # file echo the question's own terms come first (an investigator reads the
    # complaint before ranking suspicions)
    q_terms = {w for w in re.findall(r"[a-z_./]{3,}", (question or "").lower())}
    q_terms -= {"the", "and", "why", "how", "might", "does", "this", "that", "with",
                "for", "are", "can", "when", "what", "return", "http", "instead",
                "could", "would", "should"}

    def relevance(f: Finding) -> int:
        text = f"{f.title} {f.rationale} {f.file}".lower()
        return sum(1 for t in q_terms if t in text)

    uniq.sort(key=lambda f: (severity.get(f.severity, 9), -relevance(f), f.file, f.line))

    summary = _render_summary(question, trace, chain_files, uniq, tests, status)
    result = AgentResult(
        agent="issue_investigator",
        summary=summary,
        citations=citations[:10],
        findings=uniq[:8],
        extra={
            "route": ({"method": trace["route"].method, "path": trace["route"].path,
                       "handler": trace["route"].handler, "file": trace["route"].file,
                       "line": trace["route"].line} if trace and trace["route"] else None),
            "call_chain": trace["chain"][:10] if trace else [],
            "files": chain_files,
            "tests": tests,
            "status_code": status,
        },
    )
    EventTap.emit("agent", agent="issue_investigator", status="done",
                  hypotheses=len(uniq), files=len(chain_files), tests=len(tests))
    return result


def _render_summary(question, trace, chain_files, hypotheses, tests, status) -> str:
    parts: list[str] = [f"Investigation: {question.strip()}", ""]
    if trace and trace["route"]:
        parts.append(f"Endpoint: {trace['route'].method} {trace['route'].path} -> {trace['route'].handler} ({trace['route'].file}:{trace['route'].line})")
        parts.append("Call chain:")
        for hop in trace["chain"][:8]:
            indent = "  " * (hop["depth"] + 1)
            parts.append(f"{indent}└─ {hop['symbol']}  ({hop['file']}:{hop['line']})")
        parts.append("")
    elif chain_files:
        parts.append("Relevant files: " + ", ".join(chain_files[:5]))
        parts.append("")
    if hypotheses:
        parts.append(f"Ranked hypotheses ({len(hypotheses)}):")
        for i, f in enumerate(hypotheses[:5], 1):
            parts.append(f"{i}. [{f.severity}] {f.title} — {f.file}:{f.line}")
            parts.append(f"   {f.rationale}")
    else:
        parts.append("No concrete defects found by static analysis along this path.")
    parts.append("")
    parts.append("Related tests: " + (", ".join(tests[:4]) if tests else
                  "none found for the involved files (coverage gap)."))
    if status:
        parts.append(f"Question mentions status {status}: unhandled exceptions in the chain "
                     f"above would surface as HTTP {status}.")
    return "\n".join(parts)


SYSTEM_PROMPT = (
    "You are RepoPilot's Issue Investigation Agent. You receive a question, a "
    "traced call chain and a list of deterministic static-analysis findings "
    "(each with file:line evidence). Write a concise investigation report: "
    "1) the traced chain, 2) ranked hypotheses with evidence citations in "
    "`path:line` form, 3) a suggested fix. Use ONLY the provided findings and "
    "chain — do not invent new defects or files. Max 20 lines."
)


def narrate(question: str, result: AgentResult, llm) -> str:
    text = narrate_or_none(llm, SYSTEM_PROMPT,
                           f"Question: {question}\n\n{result.summary}\n\n"
                           f"Findings JSON: {result.to_dict()['findings']}")
    return text or result.summary

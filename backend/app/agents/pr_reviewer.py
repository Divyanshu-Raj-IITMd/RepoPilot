"""Agent 4 — PR Review Agent.

Parses a unified diff, maps hunks to files/lines, and runs deterministic
checks over the added lines (with repository context):

  correctness, security, performance, maintainability, tests, breaking changes

Findings look like:
  HIGH   Potential SQL injection risk        app/services/orders.py:23
and every one carries the offending line + rationale.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.agents import patterns
from app.agents.findings import AgentResult, Finding, make_citation
from app.agents.state import EventTap
from app.graph.code_graph import CodeGraph
from app.llm import narrate_or_none

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class DiffFile:
    path: str
    added: list[tuple[int, str]]      # (new-file line number, text)
    removed: list[tuple[str]]         # raw removed lines
    hunks: int = 0


def parse_unified_diff(diff: str) -> list[DiffFile]:
    files: list[DiffFile] = []
    current: DiffFile | None = None
    new_line = 0
    for line in diff.splitlines():
        m = re.match(r"^\+\+\+\s+(?:b/)?(.+?)\s*$", line)
        if m and m.group(1).strip():
            path = m.group(1).strip()
            current = DiffFile(path=path, added=[], removed=[])
            files.append(current)
            continue
        if line.startswith("---"):
            continue
        h = _HUNK_RE.match(line)
        if h and current is not None:
            current.hunks += 1
            new_line = int(h.group(1))
            continue
        if current is None:
            continue
        if line.startswith("+"):
            current.added.append((new_line, line[1:]))
            new_line += 1
        elif line.startswith("-"):
            current.removed.append((line[1:],))
        else:
            new_line += 1
    return [f for f in files if f.added or f.removed]


# ------------------------------------------------------------------- diff checks

def _check_added_lines(graph: CodeGraph, df: DiffFile) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, text in df.added:
        interpolated = re.findall(r"\{(\w+)\}", text)
        all_constants = interpolated and all(v.isupper() for v in interpolated)
        if interpolated:
            flag = not all_constants and bool(
                patterns.SQL_STRING_BUILD.search(text) or patterns.SQL_FSTRING_ANYWHERE.search(text))
        else:
            flag = bool(patterns.SQL_STRING_BUILD.search(text))
        if flag:
            findings.append(Finding(
                severity="HIGH", category="sql_injection",
                title="Potential SQL injection risk", file=df.path, line=lineno,
                snippet=text.strip()[:160],
                rationale="SQL is assembled via f-string/format/concatenation; use bound "
                          "parameters instead.",
            ))
        if patterns.DANGEROUS_CALL.search(text):
            findings.append(Finding(
                severity="HIGH", category="dangerous_call",
                title="Dangerous call introduced", file=df.path, line=lineno,
                snippet=text.strip()[:160],
                rationale="eval/exec/os.system/shell=True can execute untrusted input.",
            ))
        if patterns.BARE_EXCEPT.search(text) or re.search(
            r"^\s*except\s*(?:Exception|BaseException)?\s*(?:as\s+\w+)?\s*:\s*$", text
        ):
            # `except Exception:` with the pass/... on the following line
            findings.append(Finding(
                severity="MEDIUM", category="swallowed_error",
                title="Broad exception handler swallows errors", file=df.path,
                line=lineno, snippet=text.strip()[:160],
                rationale="Errors are silently discarded; at minimum log and re-raise or "
                          "return a precise error.",
            ))
        if patterns.MUTABLE_DEFAULT.search(text):
            findings.append(Finding(
                severity="MEDIUM", category="mutable_default",
                title="Mutable default argument", file=df.path, line=lineno,
                snippet=text.strip()[:160],
                rationale="Default []/{} is shared across every call.",
            ))
        if patterns.TODO_FIXME.search(text):
            findings.append(Finding(
                severity="LOW", category="todo",
                title="TODO/FIXME introduced in diff", file=df.path, line=lineno,
                snippet=text.strip()[:160],
                rationale="Unfinished work shipped in the PR.",
            ))
        if patterns.EQ_NONE.search(text):
            findings.append(Finding(
                severity="LOW", category="style", title="Use `is None` instead of `== None`",
                file=df.path, line=lineno, snippet=text.strip()[:160],
                rationale="PEP 8 style; identity comparison is correct for None.",
            ))
    return findings


def _check_secret_lines(df: DiffFile) -> list[Finding]:
    from app.sandbox.secret_scanner import SECRET_PATTERNS

    findings = []
    for lineno, text in df.added:
        for _kind, title, pattern in SECRET_PATTERNS:
            if re.search(pattern, text) and "environ" not in text and "getenv" not in text:
                findings.append(Finding(
                    severity="HIGH", category="hardcoded_secret",
                    title=f"{title} committed in the diff", file=df.path, line=lineno,
                    snippet=re.sub(r"[A-Za-z0-9_/+-]{6,}", lambda m: m.group(0)[:4] + "***", text)[:160],
                    rationale="Secrets must come from the environment/secret manager, "
                              "never the repository.",
                ))
                break
    return findings


_REMOVED_AUTH = re.compile(r"auth|token|Depends\(|@requires|get_current_user|verify_token|"
                           r"login_required|permission", re.I)
_REPLACEMENT_AUTH = re.compile(r"decode_token|verify_?\\w*token|verify_signature|Depends\(|"
                               r"get_current_user|require[sd]?_|auth_middleware|login_required|"
                               r"check_permissions?", re.I)


def _check_auth_removal(df: DiffFile) -> list[Finding]:
    removed_auth = [r for r, in df.removed if _REMOVED_AUTH.search(r)]
    added_auth = [t for _, t in df.added if _REPLACEMENT_AUTH.search(t)]
    if removed_auth and not added_auth:
        return [Finding(
            severity="HIGH", category="removed_auth",
            title="Authentication / token verification removed", file=df.path,
            line=df.added[0][0] if df.added else 1,
            snippet=removed_auth[0].strip()[:160],
            rationale="The diff removes an auth/token verification line without adding a "
                      "replacement — the endpoint may accept unverified input.",
        )]
    return []


def _check_loop_queries(df: DiffFile) -> list[Finding]:
    """Queries executed inside an added loop (N+1) — detected across added lines."""
    findings: list[Finding] = []
    loop_line = None
    loop_indent = -1
    for lineno, text in df.added:
        stripped = text.lstrip()
        indent = len(text) - len(stripped)
        if loop_line is not None and stripped and indent <= loop_indent:
            loop_line = None
        if re.match(r"for\s+\w+.*:\s*$", stripped):
            loop_line = (lineno, text)
            loop_indent = indent
            continue
        if loop_line is not None and re.search(
            r"\b(?:db|cursor|session|conn)\.(?:execute|query\w*|get|find|insert|update)\s*\(", text
        ):
            findings.append(Finding(
                severity="MEDIUM", category="n_plus_one",
                title="Query executed inside a loop (N+1 pattern)", file=df.path,
                line=lineno, snippet=text.strip()[:160],
                rationale="The loop body issues one query per iteration; batch the "
                          "operations instead.",
            ))
            loop_line = None
    return findings


def _check_breaking_changes(graph: CodeGraph, df: DiffFile) -> list[Finding]:
    findings = []
    removed_defs = {m.group(1): (m.group(2) or "", r)
                    for r, in df.removed
                    for m in [re.match(r"\s*def\s+(\w+)\s*\(([^)]*)\)", r)] if m}
    for lineno, text in df.added:
        m = re.match(r"\s*def\s+(\w+)\s*\(([^)]*)\)", text)
        if m and m.group(1) in removed_defs:
            old_params = {p.strip().split("=")[0].split(":")[0].strip()
                          for p in removed_defs[m.group(1)][0].split(",") if p.strip()}
            new_params = {p.strip().split("=")[0].split(":")[0].strip()
                          for p in m.group(2).split(",") if p.strip()}
            removed = old_params - new_params
            if removed:
                findings.append(Finding(
                    severity="MEDIUM", category="breaking_change",
                    title=f"Breaking change to {m.group(1)}(): parameter(s) removed: "
                          f"{', '.join(sorted(removed))}",
                    file=df.path, line=lineno, snippet=text.strip()[:160],
                    rationale="Existing callers may pass the removed parameter(s).",
                ))
    return findings


def _check_missing_tests(graph: CodeGraph, files: list[DiffFile]) -> list[Finding]:
    findings = []
    covered_modules = set()
    for rec in graph.imports:
        if rec.resolved_file:
            covered_modules.add(rec.resolved_file)
    for df in files:
        base = df.path.rsplit("/", 1)[-1]
        if base.startswith("test_") or "/tests/" in df.path:
            continue
        has_logic = any(re.search(r"\bdef\b|=>", t) for _, t in df.added)
        test_refs = graph.tests_for_files([df.path])
        if has_logic and not test_refs:
            findings.append(Finding(
                severity="MEDIUM", category="missing_tests",
                title="No unit test for the changed code", file=df.path,
                line=df.added[0][0] if df.added else 1,
                snippet=(df.added[0][1].strip()[:120] if df.added else ""),
                rationale=f"No test file imports or references {df.path}.",
            ))
    return findings


def _check_long_functions(graph: CodeGraph, files: list[DiffFile]) -> list[Finding]:
    findings = []
    for df in files:
        for sym in graph.symbols_by_file.get(df.path, []):
            if sym.kind != "class" and (sym.end_line - sym.start_line) > 80:
                findings.append(Finding(
                    severity="LOW", category="maintainability",
                    title=f"{sym.qualified} is {sym.end_line - sym.start_line} lines long",
                    file=df.path, line=sym.start_line, snippet=sym.signature,
                    rationale="Long functions are hard to test and review; consider "
                              "extracting helpers.",
                ))
    return findings


# ----------------------------------------------------------------------- agent

def review(repo, diff: str) -> AgentResult:
    EventTap.emit("agent", agent="pr_reviewer", status="started", diff_lines=len(diff.splitlines()))
    g = repo.graph
    files = parse_unified_diff(diff)
    if not files:
        return AgentResult(
            agent="pr_reviewer",
            summary="No parsable file changes found in the provided diff.",
            extra={"files": []},
        )

    findings: list[Finding] = []
    for df in files:
        findings.extend(_check_added_lines(g, df))
        findings.extend(_check_secret_lines(df))
        findings.extend(_check_auth_removal(df))
        findings.extend(_check_breaking_changes(g, df))
        findings.extend(_check_loop_queries(df))
    findings.extend(_check_missing_tests(g, files))
    findings.extend(_check_long_functions(g, files))

    # repository-context checks, restricted to lines the diff actually touches
    for df in files:
        if df.path not in g.files:
            continue
        touched = {ln for ln, _ in df.added}
        for f in patterns.find_sql_injection(g, [df.path]) + \
                patterns.find_none_deref(g, [df.path]) + \
                patterns.find_n_plus_one(g, [df.path]):
            if any(abs(f.line - t) <= 5 for t in touched):
                findings.append(f)

    # dedupe + sort
    seen: set[tuple] = set()
    uniq: list[Finding] = []
    for f in findings:
        key = (f.category, f.file, f.line, f.title)
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    uniq.sort(key=lambda f: (order.get(f.severity, 9), f.file, f.line))

    citations = []
    for f in uniq[:12]:
        citations.append(make_citation(g, f.file, f.line, f.line, reason=f.rationale))

    counts = {s: sum(1 for f in uniq if f.severity == s) for s in ("HIGH", "MEDIUM", "LOW")}
    summary = _render(uniq, counts, [df.path for df in files])
    result = AgentResult(
        agent="pr_reviewer", summary=summary, citations=citations,
        findings=uniq,
        extra={"files": [df.path for df in files], "counts": counts},
    )
    EventTap.emit("agent", agent="pr_reviewer", status="done",
                  findings=len(uniq), **{f"{k.lower()}_count": v for k, v in counts.items()})
    return result


def _render(findings: list[Finding], counts: dict, files: list[str]) -> str:
    parts = [f"Reviewed {len(files)} changed file(s): {', '.join(files[:6])}", ""]
    parts.append(f"Findings: {counts.get('HIGH', 0)} HIGH / {counts.get('MEDIUM', 0)} "
                 f"MEDIUM / {counts.get('LOW', 0)} LOW")
    parts.append("")
    for f in findings:
        parts.append(f"[{f.severity}] {f.title} — {f.file}:{f.line}")
        if f.snippet:
            parts.append(f"    {f.snippet[:120]}")
    if not findings:
        parts.append("No issues detected by the deterministic checks.")
    return "\n".join(parts)


SYSTEM_PROMPT = (
    "You are RepoPilot's PR Review Agent. You receive deterministic findings "
    "from static analysis of a diff. Write a professional review: an overall "
    "verdict (approve / request changes) plus the findings grouped by "
    "severity, each with `path:line`. Do not add findings that are not in the "
    "list. Max 15 lines."
)


def narrate(result: AgentResult, llm) -> str:
    text = narrate_or_none(llm, SYSTEM_PROMPT, result.summary)
    return text or result.summary

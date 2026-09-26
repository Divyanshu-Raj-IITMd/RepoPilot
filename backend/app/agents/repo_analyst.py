"""Agent 1 — Repository Analyst.

Deterministically derives the repository architecture: frameworks, databases,
entry point, directory roles, endpoint inventory. LLM narration optional.
"""

from __future__ import annotations

from app.agents.findings import AgentResult, make_citation
from app.agents.state import EventTap
from app.llm import narrate_or_none


def analyze(repo, question: str = "") -> AgentResult:
    EventTap.emit("agent", agent="repo_analyst", status="started")
    s = repo.summary
    g = repo.graph

    def role_dir(role: str) -> str:
        dirs = s.dir_roles.get(role, [])
        return dirs[0] + "/" if dirs else "(not found)"

    def role_files(role: str, n: int = 2) -> str:
        dirs = s.dir_roles.get(role, [])
        files = []
        for d in dirs:
            files.extend(p for p in g.files if p.startswith(d + "/"))
        return ", ".join(files[:n])

    lines = [
        f"Repository: {repo.name}",
        "Languages: " + (", ".join(f"{k} ({v} files)" for k, v in list(s.languages.items())[:5]) or "n/a"),
        "Frameworks: " + (", ".join(s.frameworks) or "n/a"),
        "Database: " + (", ".join(s.databases) or "n/a"),
        "Main entry: " + (s.entry_points[0] if s.entry_points else "(not detected)"),
        f"Authentication: {role_dir('authentication')} ({role_files('authentication')})",
        f"API: {role_dir('api')} ({role_files('api')})",
        f"Business logic: {role_dir('business logic')} ({role_files('business logic')})",
        f"Data access: {role_dir('data access')} ({role_files('data access')})",
        f"Models: {role_dir('models')} ({role_files('models')})",
        "Tests: " + (", ".join(s.test_files[:4]) or "(none found)"),
        "",
        f"{s.file_count} files, {s.loc:,} lines, {len(g.symbols)} symbols, "
        f"{len(g.routes)} HTTP endpoints.",
    ]

    citations = []
    for ep in s.entry_points[:1]:
        citations.append(make_citation(g, ep, 1, min(20, g.files[ep].lines),
                                       "application entry point"))
    for role in ("authentication", "api", "business logic", "data access"):
        d = s.dir_roles.get(role, [])
        if d:
            f = next((p for p in g.files if p.startswith(d[0] + "/")), None)
            if f:
                citations.append(make_citation(g, f, 1, 10, f"{role} layer"))

    result = AgentResult(
        agent="repo_analyst",
        summary="\n".join(lines),
        citations=citations,
        extra={
            "languages": s.languages, "frameworks": s.frameworks,
            "databases": s.databases, "entry_points": s.entry_points,
            "dir_roles": s.dir_roles, "endpoints": [
                {"method": r.method, "path": r.path, "handler": r.handler,
                 "file": r.file, "line": r.line} for r in g.routes],
            "loc": s.loc, "files": s.file_count, "symbols": len(g.symbols),
            "test_files": s.test_files,
        },
    )
    EventTap.emit("agent", agent="repo_analyst", status="done",
                  endpoints=len(g.routes), frameworks=s.frameworks)
    return result


SYSTEM_PROMPT = (
    "You are RepoPilot's Repository Analyst. You receive a structured, "
    "deterministic analysis of a repository. Summarize the architecture in at "
    "most 12 short lines. Only use facts from the provided data. Do not invent files."
)


def narrate(repo, result: AgentResult, llm) -> str:
    text = narrate_or_none(llm, SYSTEM_PROMPT, str(result.extra))
    return text or result.summary

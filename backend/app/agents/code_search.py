"""Agent 2 — Code Search Agent.

Answers "where is X implemented?" with ranked, auditable evidence:
file, line range, code context and *why* each file matched. Also explains
the execution flow using the code graph when one is derivable.
"""

from __future__ import annotations

import re

from app.agents.findings import AgentResult, Citation
from app.agents.state import EventTap
from app.llm import narrate_or_none

_STOP = {"where", "is", "the", "a", "an", "implemented", "in", "this", "repo",
         "repository", "code", "codebase", "find", "which", "file", "files",
         "located", "does", "do", "and", "of", "to", "how", "what", "used",
         "handled", "handle", "defined", "definition"}


def _query_terms(question: str) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]+|/\S+", question)
    return [w for w in words if w.lower() not in _STOP]


_DEP_QUESTION = re.compile(
    r"which files? (?:import|include)|which files? does|who imports|files? that import|"
    r"what does .* (?:import|include|depend on)|depends? on|"
    r"who (?:calls|uses)|callers? of|used by|imported by", re.I)
_DIR_WORDS = ("auth", "middleware", "routes", "services", "models",
              "repositories", "utils", "tests")
_MENTION_FILE = re.compile(r"\b([\w./-]*app[\w./-]*|[\w-]+/[\w./-]+|\w+\.(?:py|js|ts|go))")
_MENTION_SYMBOL = re.compile(
    r"(?:who (?:calls|uses)|callers? of|used by)\s+(?:the )?(?:function |method )?`?(\w+)`?", re.I)


def _dependency_citations(repo, question: str):
    """Answer dependency questions directly from the code graph (exact, deterministic)."""
    g = repo.graph
    cites: list[Citation] = []
    summary = ""

    def resolve_file(mention: str):
        mention = mention.strip().strip("?.!").rstrip("/")
        for cand in (mention, mention + ".py", mention.replace(".", "/") + ".py"):
            if cand in g.files:
                return cand
        return None

    # symbol callers: "who calls X", "callers of X", "who uses X"
    m = _MENTION_SYMBOL.search(question)
    if m:
        syms = g.find_symbol(m.group(1))
        if syms:
            sym = syms[0]
            callers = g.callers(sym.file, sym.qualified)
            for c_file, c_sym in callers[:6]:
                s = g.get_symbol(c_file, c_sym)
                line = s.start_line if s else 1
                cites.append(Citation(
                    file=c_file, start_line=line, end_line=line + 2,
                    symbol=c_sym, snippet="",
                    reason=f"calls {sym.qualified} ({sym.file})"))
            summary = (f"`{sym.qualified}` is called from {len(callers)} place(s): "
                       + ", ".join(f"{f}::{s}" for f, s in callers[:6]))
            return cites, summary

    # file-level: "which files import X" (dependents) / "what does X depend on"
    mentions = _MENTION_FILE.findall(question)
    if not mentions:
        # word mentions: "what does the middleware import?"
        low = question.lower()
        for word in _DIR_WORDS:
            if re.search(rf"\bthe {word}\b|\b{word} (?:module|layer|file)\b", low):
                mentions = [word]
                break
    for mention in mentions:
        target = resolve_file(mention)
        if not target and mention in _DIR_WORDS:
            files_in_dir = [p for p in g.files
                            if f"/{mention}/" in f"/{p}" and not p.endswith("__init__.py")]
            if files_in_dir:
                target = sorted(files_in_dir)[0]
        if not target:
            continue
        outbound = bool(re.search(
            r"(?:what|which files) does .* (?:depend on|import|include)", question, re.I))
        if outbound:
            related = sorted(g.file_dependencies.get(target, set()))
            direction = "imports / depends on"
        else:
            related = sorted(g.file_dependents.get(target, set()))
            direction = "is imported by"
        short = mention.split("/")[-1].replace(".py", "")
        target_sf = g.files.get(target)
        for f in related[:6]:
            sf = g.files.get(f)
            if not sf:
                continue
            line_no, imported_names = 1, ""
            if outbound and target_sf is not None:
                # find the import statement in the TARGET that pulls in f
                f_short = f.rsplit("/", 1)[-1].replace(".py", "")
                f_mod = f.rsplit("/", 1)[0].replace("/", ".")
                for i, ln in enumerate(target_sf.content.splitlines(), 1):
                    if "import" in ln and (f_short in ln or f_mod.split(".")[-1] in ln):
                        line_no = i
                        imported_names = ln.strip()[:90]
                        break
            else:
                for i, ln in enumerate(sf.content.splitlines(), 1):
                    if "import" in ln and (short in ln or mention in ln):
                        line_no = i
                        names = re.findall(r"import\s+(?:.*)", ln)
                        imported_names = names[0][:80] if names else ln.strip()[:80]
                        break
            reason = (f"dependency of {target}" if outbound else f"imports {target}")
            cites.append(Citation(file=f, start_line=line_no, end_line=line_no,
                                  snippet="", reason=reason
                                  + (f" ({imported_names})" if imported_names else "")))
        if related:
            summary = f"`{target}` {direction}: " + ", ".join(related[:8])
        return cites, summary
    return cites, summary


def search(repo, question: str, k: int = 8) -> AgentResult:
    EventTap.emit("agent", agent="code_search", status="started", question=question)
    sr = repo.retriever.search(question, k=k)
    terms = _query_terms(question)

    # dependency questions get a graph answer first (deterministic, exact)
    dep_cites: list[Citation] = []
    dep_summary = ""
    if _DEP_QUESTION.search(question):
        dep_cites, dep_summary = _dependency_citations(repo, question)

    citations: list[Citation] = []
    per_file: dict[str, int] = {}
    seen_files: set[str] = set()
    for hit in sr.hits:
        is_test = "test" in hit.file
        if per_file.get(hit.file, 0) >= (1 if not is_test else 0):
            continue
        cite = hit.citation()
        citations.append(Citation(file=cite["file"], start_line=cite["start_line"],
                                  end_line=cite["end_line"], snippet=cite["snippet"],
                                  reason=hit.reason, symbol=cite.get("symbol")))
        per_file[hit.file] = per_file.get(hit.file, 0) + 1
        seen_files.add(hit.file)
        if len(citations) >= 5:
            break

    # graph completion: who *calls* the top matched symbols? (execution flow)
    g = repo.graph
    added_callers = 0
    for cite in list(citations):
        if added_callers >= 2 or cite.symbol is None or cite.symbol.startswith("test_"):
            continue
        for c_file, c_sym in g.callers(cite.file, cite.symbol)[:2]:
            if c_file in seen_files or "test" in c_file:
                continue
            sym = g.get_symbol(c_file, c_sym)
            if sym:
                citations.append(Citation(
                    file=c_file, start_line=sym.start_line, end_line=min(sym.end_line, sym.start_line + 12),
                    snippet="", symbol=c_sym,
                    reason=f"calls {cite.symbol} ({cite.file}) — part of the execution flow",
                ))
                seen_files.add(c_file)
                added_callers += 1
    # fill snippets for caller citations
    for cite in citations:
        if not cite.snippet:
            sf = g.files.get(cite.file)
            if sf:
                lines = sf.content.splitlines()
                cite.snippet = "\n".join(lines[cite.start_line - 1: cite.end_line])[:1200]

    # test-coverage questions: cite the test files that cover the top evidence
    if re.search(r"test file|tests? for|covers|covered by|test coverage", question, re.I):
        if not any("test" in c.file for c in citations) and citations:
            for tf in g.tests_for_files([citations[0].file])[:2]:
                if tf not in seen_files:
                    lines = g.files[tf].content.splitlines()
                    citations.append(Citation(
                        file=tf, start_line=1, end_line=min(10, len(lines)),
                        snippet="\n".join(lines[:10])[:800],
                        reason=f"test file covering {citations[0].file}"))
                    seen_files.add(tf)

    # Explain a flow across the top files using the call graph.
    flow = _explain_flow(repo, sr, terms)

    files_line = ", ".join(dict.fromkeys(c.file for c in citations)) or "(no matches)"
    summary_parts = [
        f"Top evidence for '{' '.join(terms) or question}': {files_line}.",
    ]
    if dep_summary:
        summary_parts.insert(0, dep_summary)
        citations = dep_cites + citations
    if flow:
        summary_parts.append("\nExecution flow:\n" + flow)
    result = AgentResult(
        agent="code_search",
        summary="\n".join(summary_parts),
        citations=citations[:8],
        extra={"query_terms": terms,
               "files": list(seen_files | {c.file for c in dep_cites}),
               "symbols": [s.qualified for s in sr.symbols][:10],
               "dependency_answer": dep_summary or None},
    )
    EventTap.emit("agent", agent="code_search", status="done",
                  files=list(seen_files | {c.file for c in dep_cites})[:6])
    return result


def _explain_flow(repo, sr, terms: list[str]) -> str:
    """Order evidence as a request flow when the graph links the top files."""
    g = repo.graph
    steps: list[str] = []
    # Prefer middleware/entry-ish files first, then routes, then services.
    def rank(f: str) -> int:
        if "middleware" in f:
            return 0
        if "/routes/" in f or "/api/" in f:
            return 1
        if "/services/" in f:
            return 2
        return 3
    files = sorted(dict.fromkeys(h.file for h in sr.hits[:6]), key=rank)
    if len(files) < 2:
        return ""
    for f in files:
        sf = g.files.get(f)
        if not sf:
            continue
        # find the most relevant symbol in this file among search hits
        sym = next((h.chunk.get("symbol") for h in sr.hits[:10]
                    if h.file == f and h.chunk.get("symbol")), None)
        line = next((h.chunk.get("start_line", 1) for h in sr.hits[:10] if h.file == f), 1)
        label = sym or f.rsplit("/", 1)[-1]
        steps.append(f"  {f}:{line} — {label}")
    return "\n".join(steps[:5])


SYSTEM_PROMPT = (
    "You are RepoPilot's Code Search Agent. You receive a question and a list "
    "of evidence chunks (file, lines, code, reason) retrieved from the "
    "repository. Answer the question in at most 10 lines. Cite every claim as "
    "`path:line`. Use ONLY the provided evidence — never mention files or "
    "symbols that are not in the evidence. End with a one-line 'Flow:' "
    "description when the evidence shows how components connect."
)


def _context_line(citation: Citation, terms: list[str]) -> str:
    """Best-matching line of the snippet for display in the answer."""
    lines = [ln for ln in (citation.snippet or "").splitlines() if ln.strip()]
    if not lines:
        return ""
    best, best_score = "", -1
    for raw in lines:
        low = raw.lower()
        score = sum(1 for t in terms if t in low or (len(t) >= 3 and t[:3] in low))
        if score > best_score:
            best, best_score = raw.strip()[:110], score
    if best_score <= 0:
        for cand in lines:
            s = cand.strip()
            if not s.startswith(("file:", "symbols:", "imports:", "depends", "---", "endpoint:",
                                 "handler:", "doc:")) and len(s) > 3:
                return s[:110]
        return ""
    return best


def narrate(question: str, result: AgentResult, llm) -> str:
    if not result.citations:
        return "No matching code found for this question."
    terms = result.extra.get("query_terms") or _query_terms(question)
    evidence = "\n\n".join(
        f"[{i+1}] {c.file}:{c.start_line}-{c.end_line} (symbol: {c.symbol or '—'}) "
        f"reason: {c.reason}\n```{c.snippet[:600]}```"
        for i, c in enumerate(result.citations)
    )
    text = narrate_or_none(llm, SYSTEM_PROMPT, f"Question: {question}\n\nEvidence:\n{evidence}")
    if text:
        return text
    # Deterministic fallback narration
    lines: list[str] = []
    dep = result.extra.get("dependency_answer")
    if dep:
        lines.append(dep)
        lines.append("")
    lines.append(f"Found {len(result.citations)} matching location(s):")
    for i, c in enumerate(result.citations, 1):
        label = c.symbol or _context_line(c, terms) or c.file
        lines.append(f"{i}. {c.file}:{c.start_line}-{c.end_line} — {label}")
        ctx = _context_line(c, terms)
        if ctx and ctx != label:
            lines.append(f"   context: {ctx}")
        if c.reason:
            lines.append(f"   why: {c.reason}")
    if result.extra.get("symbols"):
        lines.append(f"Related symbols: {', '.join(result.extra['symbols'][:6])}")
    return "\n".join(lines)

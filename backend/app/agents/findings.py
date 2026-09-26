"""Evidence types shared by all agents.

Every agent returns an AgentResult composed of:
  * a human summary,
  * citations (file + line range + snippet + reason) — always derived from
    the deterministic retrieval/graph layers, never invented by the LLM,
  * findings (severity-tagged issues),
  * arbitrary structured extras.

The LLM (when available) only *narrates* the evidence pack; it cannot add
citations that the pipeline did not produce. That is what makes RepoPilot's
answers auditable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


@dataclass
class Citation:
    file: str
    start_line: int
    end_line: int
    snippet: str = ""
    reason: str = ""
    symbol: str | None = None

    def to_dict(self) -> dict:
        return {"file": self.file, "start_line": self.start_line, "end_line": self.end_line,
                "snippet": self.snippet, "reason": self.reason, "symbol": self.symbol}


@dataclass
class Finding:
    severity: str  # HIGH | MEDIUM | LOW
    category: str
    title: str
    file: str
    line: int
    snippet: str = ""
    rationale: str = ""

    def to_dict(self) -> dict:
        return {"severity": self.severity, "category": self.category, "title": self.title,
                "file": self.file, "line": self.line, "snippet": self.snippet,
                "rationale": self.rationale}


@dataclass
class AgentResult:
    agent: str
    summary: str
    citations: list[Citation] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "summary": self.summary,
            "citations": [c.to_dict() for c in self.citations],
            "findings": sorted((f.to_dict() for f in self.findings),
                               key=lambda f: SEVERITY_ORDER.get(f["severity"], 9)),
            "extra": self.extra,
        }


def make_citation(graph, file: str, start: int, end: int, reason: str,
                  symbol: str | None = None, context: int = 0) -> Citation:
    """Build a citation with a real snippet taken from the indexed file."""
    sf = graph.files.get(file)
    snippet = ""
    if sf:
        lines = sf.content.splitlines()
        s = max(1, start - context)
        e = min(len(lines), end + context)
        snippet = "\n".join(lines[s - 1: e])[:1500]
    return Citation(file=file, start_line=start, end_line=end, snippet=snippet,
                    reason=reason, symbol=symbol)

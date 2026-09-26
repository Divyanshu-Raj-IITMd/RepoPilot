"""Hybrid retrieval: dense vectors + lexical overlap + symbol/route lookup + graph expansion.

Every result carries file/line evidence so every agent answer is auditable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.graph.code_graph import CodeGraph
from app.indexing.embedder import tokenize
from app.indexing.indexer import CodeIndex

_PATH_HINT_RE = re.compile(r"(/[A-Za-z0-9_\-./{}]*)")
_FILE_HINT_RE = re.compile(r"([\w./-]+\.(?:py|js|ts|tsx|go|java|rb|rs))")

# Natural-language verb intents -> implementation-verb prefixes. "Where are
# tokens created?" should boost create_*/encode_*/build_* symbols.
_VERB_INTENT = {
    "created": ("create", "encode", "build", "make", "new", "generate"),
    "checked": ("check", "verify", "validate", "assert"),
    "verified": ("verify", "check", "validate"),
    "validated": ("validate", "verify", "check"),
    "handled": ("handle", "process"),
    "generated": ("generate", "create", "encode"),
    "stored": ("store", "save", "persist", "write"),
    "loaded": ("load", "fetch", "get", "read"),
    "defined": ("define", "declare"),
    "computed": ("compute", "calculate", "evaluate"),
}


@dataclass
class Retrieved:
    chunk: dict
    score: float
    reason: str = ""
    vec_score: float = 0.0
    kw_score: float = 0.0

    @property
    def file(self) -> str:
        return self.chunk["file"]

    @property
    def lines(self) -> tuple[int, int]:
        return (self.chunk["start_line"], self.chunk["end_line"])

    def citation(self) -> dict:
        snippet = self.chunk["text"]
        return {
            "file": self.chunk["file"],
            "start_line": self.chunk["start_line"],
            "end_line": self.chunk["end_line"],
            "symbol": self.chunk.get("symbol"),
            "kind": self.chunk["kind"],
            "snippet": snippet[:1200],
            "reason": self.reason,
        }


@dataclass
class SearchResult:
    hits: list[Retrieved] = field(default_factory=list)
    symbols: list = field(default_factory=list)
    routes: list = field(default_factory=list)
    files: list[str] = field(default_factory=list)


class Retriever:
    def __init__(self, graph: CodeGraph, index: CodeIndex, top_k: int = 10) -> None:
        self.graph = graph
        self.index = index
        self.top_k = top_k
        self._chunk_tokens: list[set[str]] = [set(tokenize(c["text"])) for c in index.chunks]

    # ------------------------------------------------------------------ search

    def search(self, query: str, k: int | None = None, kinds: tuple[str, ...] | None = None) -> SearchResult:
        k = k or self.top_k
        result = SearchResult()

        # 1) exact-ish route lookup for endpoint questions
        for m in _PATH_HINT_RE.findall(query):
            route = self.graph.find_route(m)
            if route:
                result.routes.append(route)

        # 2) symbol lookup for "function `foo`" questions
        for name in re.findall(r"`(\w+)`|def\s+(\w+)|function\s+(\w+)", query):
            for hit in filter(None, name):
                result.symbols.extend(self.graph.find_symbol(hit)[:5])

        # 3) dense + lexical hybrid scoring over all chunks
        dense = {c["id"]: (c, s) for c, s in self.index.vector_search(query, k=max(k * 3, 24))}
        q_tokens = set(tokenize(query))
        q_path_tokens = set(tokenize(query.replace("/", " ")))
        scored: list[Retrieved] = []
        for i, chunk in enumerate(self.index.chunks):
            if kinds and chunk["kind"] not in kinds:
                continue
            vec = dense.get(chunk["id"])
            vec_score = vec[1] if vec else 0.0
            ctoks = self._chunk_tokens[i]
            overlap = len(q_tokens & ctoks)
            kw = overlap / (len(q_tokens) ** 0.5 + 1e-9) if q_tokens else 0.0
            path_boost = 0.0
            for pt in q_path_tokens:
                if len(pt) > 2 and pt in chunk["file"].lower():
                    path_boost += 0.08
            sym_boost = 0.0
            if chunk.get("symbol"):
                sym_name = chunk["symbol"].split(".")[-1].lower()
                if sym_name and sym_name in q_tokens:
                    sym_boost = 0.35
                else:
                    verbs: set[str] = set()
                    for t in q_tokens:
                        verbs.update(_VERB_INTENT.get(t, ()))
                    for v in verbs:
                        if sym_name.startswith(v + "_") or sym_name == v:
                            sym_boost = 0.30
                            break
            score = 0.55 * vec_score + 0.45 * min(kw, 1.0) + path_boost + sym_boost
            # route chunks win for endpoint queries
            if result.routes and chunk["kind"] == "route":
                if any(r.handler == chunk.get("symbol") and r.file == chunk["file"] for r in result.routes):
                    score += 0.6
            if chunk["kind"] == "file":
                score *= 0.85  # prefer precise symbol chunks
            if score > 0.02:
                scored.append(Retrieved(chunk=chunk, score=score, vec_score=vec_score,
                                        kw_score=kw, reason=self._reason(chunk, vec_score, kw)))

        scored.sort(key=lambda r: -r.score)

        # 4) graph expansion: pull in 1-hop graph neighbours of the top files
        top_files: set[str] = {r.file for r in scored[:3]}
        expanded: dict[str, Retrieved] = {}
        for f in list(top_files):
            for dep in list(self.graph.file_dependencies.get(f, set()))[:3]:
                for cand in scored:
                    if cand.file == dep and cand.chunk["kind"] == "symbol":
                        expanded.setdefault(
                            f"{cand.file}:{cand.chunk.get('symbol')}",
                            Retrieved(chunk=cand.chunk, score=cand.score * 0.55,
                                      reason=f"graph neighbour of {f} (import dependency)",
                                      vec_score=cand.vec_score, kw_score=cand.kw_score),
                        )
        for r in expanded.values():
            if r not in scored:
                scored.append(r)
        scored.sort(key=lambda r: -r.score)

        result.hits = scored[:k]
        result.files = list(dict.fromkeys(r.file for r in scored[:k]))
        return result

    @staticmethod
    def _reason(chunk: dict, vec_score: float, kw_score: float) -> str:
        bits = []
        if kw_score >= 0.25:
            bits.append("strong term overlap with the question")
        elif kw_score > 0.05:
            bits.append("partial term overlap")
        if vec_score >= 0.35:
            bits.append("high semantic similarity")
        elif vec_score > 0.15:
            bits.append("semantic similarity")
        if chunk["kind"] == "route":
            bits.append("HTTP endpoint definition")
        if chunk["kind"] == "file":
            bits.append("module structure overview")
        if not bits:
            bits.append("retrieved from the repository index")
        return "; ".join(bits)

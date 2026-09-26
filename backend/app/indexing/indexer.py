"""Indexer: chunk a repository into retrievable units and embed them.

Chunk types:
  * symbol  — one function/class, headed with file path + signature + docstring
  * file    — a structural overview chunk per file (path, symbols, imports)
  * route   — one HTTP endpoint (method + path + handler)
  * doc     — documentation files (README, etc.)
"""

from __future__ import annotations

from app.graph.code_graph import CodeGraph
from app.indexing.embedder import BaseEmbedder, get_embedder
from app.indexing.store import VectorStore
from app.parsing.models import SourceFile, Symbol


class CodeIndex:
    """A built (and persisted) semantic index over a repository."""

    def __init__(self, graph: CodeGraph, chunks: list[dict], store: VectorStore,
                 embedder: BaseEmbedder) -> None:
        self.graph = graph
        self.chunks = chunks
        self.store = store
        self.embedder = embedder

    # -------------------------------------------------------------- retrieval

    def vector_search(self, query: str, k: int) -> list[tuple[dict, float]]:
        if len(self.store) == 0:
            return []
        qvec = self.embedder.embed([query])[0]
        scores, idxs = self.store.search(qvec, min(k, len(self.store)))
        return [(self.chunks[int(i)], float(s)) for i, s in zip(idxs, scores, strict=False) if int(i) < len(self.chunks)]


def _symbol_chunk(sym: Symbol, sf: SourceFile) -> dict:
    lines = sf.content.splitlines()
    body = "\n".join(lines[sym.start_line - 1: min(sym.end_line, sym.start_line + 60)])
    header = f"file: {sym.file}\n{sym.kind} {sym.qualified}\n{sym.signature}"
    if sym.docstring:
        header += f"\n{sym.docstring.splitlines()[0]}"
    if sym.decorators:
        header += "\ndecorators: " + ", ".join(sym.decorators)
    text = f"{header}\n{body}"
    return {
        "id": f"sym:{sym.file}:{sym.qualified}:{sym.start_line}",
        "kind": "symbol", "file": sym.file, "start_line": sym.start_line,
        "end_line": sym.end_line, "symbol": sym.qualified, "text": text,
    }


def _file_chunk(sf: SourceFile, graph: CodeGraph) -> dict:
    syms = graph.symbols_by_file.get(sf.path, [])[:40]
    imports = [r.module for r in graph.imports if r.file == sf.path and r.module][:25]
    dep_files = sorted(graph.file_dependencies.get(sf.path, set()))[:15]
    text = (
        f"file: {sf.path} ({sf.language})\n"
        f"symbols: {', '.join(s.qualified for s in syms) or '(none)'}\n"
        f"imports: {', '.join(imports) or '(none)'}\n"
        f"depends on: {', '.join(dep_files) or '(none)'}\n"
        f"---\n{sf.content[:2500]}"
    )
    return {"id": f"file:{sf.path}", "kind": "file", "file": sf.path,
            "start_line": 1, "end_line": min(sf.lines, 40), "symbol": None, "text": text}


def _route_chunk(route, graph: CodeGraph) -> dict:
    handler = graph.get_symbol(route.file, route.handler)
    sig = handler.signature if handler else ""
    lines = graph.files[route.file].content.splitlines() if route.file in graph.files else []
    body = "\n".join(lines[route.line - 1: route.line + 14]) if lines else ""
    return {
        "id": f"route:{route.method}:{route.path}", "kind": "route", "file": route.file,
        "start_line": route.line, "end_line": route.line + 12, "symbol": route.handler,
        "text": (f"endpoint: {route.method} {route.path} ({route.framework})\n"
                 f"handler: {route.handler} {sig}\nfile: {route.file}\n{body}"),
    }


def _doc_chunk(sf: SourceFile) -> dict:
    return {"id": f"doc:{sf.path}", "kind": "doc", "file": sf.path,
            "start_line": 1, "end_line": min(sf.lines, 200), "symbol": None,
            "text": f"doc: {sf.path}\n{sf.content[:4000]}"}


def _env_chunk(sf: SourceFile) -> dict:
    """Config/env files are indexed REDACTED — never leak secrets into prompts."""
    from app.sandbox.secret_scanner import redact
    return {"id": f"doc:{sf.path}", "kind": "doc", "file": sf.path,
            "start_line": 1, "end_line": min(sf.lines, 100), "symbol": None,
            "text": f"config: {sf.path} (redacted)\n{redact(sf.content)[:3000]}"}


def build_index(graph: CodeGraph, settings, persist_path: str | None = None) -> CodeIndex:
    """Chunk + embed + (optionally) persist the index for a parsed repository."""
    chunks: list[dict] = []
    for path, sf in graph.files.items():
        if sf.language in ("markdown", "rst", "text"):
            chunks.append(_doc_chunk(sf))
        elif sf.language in ("env", "ini", "cfg", "yaml", "toml"):
            chunks.append(_env_chunk(sf))
        for sym in graph.symbols_by_file.get(path, []):
            if sym.kind == "class" and not sym.docstring and (sym.end_line - sym.start_line) > 40:
                continue  # very large undocumented classes stay in the file chunk
            chunks.append(_symbol_chunk(sym, sf))
        if sf.language in ("python", "javascript", "typescript"):
            chunks.append(_file_chunk(sf, graph))
    for route in graph.routes:
        chunks.append(_route_chunk(route, graph))

    embedder = get_embedder(settings)
    texts = [c["text"] for c in chunks]
    embedder.fit(texts)
    vectors = embedder.embed(texts)
    store = VectorStore(dim=embedder.dim)
    store.add(vectors)

    index = CodeIndex(graph=graph, chunks=chunks, store=store, embedder=embedder)
    if persist_path:
        store.save(persist_path, embedder.state() or {}, chunks)
    return index


def load_index(persist_path: str, graph: CodeGraph, settings) -> CodeIndex | None:
    """Load a persisted index; returns None if missing/stale."""
    from app.indexing.embedder import HashingTfidfEmbedder

    loaded = VectorStore.load(persist_path)
    if loaded is None:
        return None
    store, embedder_state, chunks = loaded
    embedder = get_embedder(settings)
    if isinstance(embedder, HashingTfidfEmbedder) and embedder_state.get("idf"):
        embedder.load_state(embedder_state)
    if len(store) != len(chunks):
        return None
    return CodeIndex(graph=graph, chunks=chunks, store=store, embedder=embedder)

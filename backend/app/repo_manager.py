"""RepoManager: the pipeline that turns a repo source into a searchable LoadedRepo.

Steps: clone/load -> walk -> detect -> parse (AST/heuristic) -> CodeGraph
       -> secret scan -> chunk+embed index -> cached in memory + on disk.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass, field

from app.config import Settings, get_settings
from app.graph.code_graph import CodeGraph
from app.indexing.indexer import build_index
from app.ingestion.cloner import IngestError, clone_or_load
from app.ingestion.detectors import detect_summary
from app.ingestion.walker import walk_repository
from app.parsing import ast_python
from app.parsing import heuristic as heuristic_parser
from app.parsing import treesitter as ts_mod
from app.parsing.models import CallEdge, ImportRecord, RepoSummary, RouteInfo, Symbol
from app.retrieval.retriever import Retriever
from app.sandbox.secret_scanner import SecurityScan, scan_files

log = logging.getLogger("repopilot.repos")


@dataclass
class LoadedRepo:
    repo_id: str
    name: str
    source: str
    root: str
    summary: RepoSummary
    graph: CodeGraph
    retriever: Retriever
    security: SecurityScan
    indexed_at: float = field(default_factory=time.time)

    def overview(self) -> dict:
        s = self.summary
        return {
            "repo_id": self.repo_id, "name": self.name, "source": self.source,
            "languages": s.languages, "frameworks": s.frameworks, "databases": s.databases,
            "entry_points": s.entry_points, "dir_roles": s.dir_roles,
            "file_count": s.file_count, "loc": s.loc, "test_files": s.test_files,
            "endpoints": [
                {"method": r.method, "path": r.path, "handler": r.handler, "file": r.file, "line": r.line}
                for r in self.graph.routes
            ][:80],
            "security_findings": [f.to_dict() for f in self.security.findings],
            "symbols": len(self.graph.symbols),
        }


class RepoManager:
    """In-memory registry of loaded repositories with disk persistence."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self._repos: dict[str, LoadedRepo] = {}
        self.registry = self._load_registry()

    # ---------------------------------------------------------------- registry

    def _load_registry(self) -> dict:
        if os.path.exists(self.settings.registry_path):
            try:
                with open(self.settings.registry_path, encoding="utf-8") as fh:
                    return json.load(fh)
            except Exception:
                return {}
        return {}

    def _save_registry(self) -> None:
        with open(self.settings.registry_path, "w", encoding="utf-8") as fh:
            json.dump(self.registry, fh, indent=2)

    @staticmethod
    def _slugify(source: str) -> str:
        base = source.rstrip("/").rsplit("/", 1)[-1] or source
        base = base.removesuffix(".git")
        return re.sub(r"[^a-z0-9-]+", "-", base.lower()).strip("-") or "repo"

    # ------------------------------------------------------------------ ingest

    def ingest(self, source: str, repo_id: str | None = None, name: str | None = None,
               refresh: bool = False) -> LoadedRepo:
        repo_id = repo_id or self._slugify(source)
        if not refresh and repo_id in self._repos:
            return self._repos[repo_id]

        t0 = time.time()
        root = clone_or_load(source, self.settings.clones_dir)
        files = walk_repository(root)
        if not files:
            raise IngestError("no indexable source files found in repository")

        summary = detect_summary(name or repo_id, files)
        symbols: list[Symbol] = []
        imports: list[ImportRecord] = []
        calls: list[CallEdge] = []
        routes: list[RouteInfo] = []

        for sf in files:
            if sf.language == "python":
                parsed = ast_python.parse_python(sf)
                if parsed.ok:
                    symbols.extend(parsed.symbols)
                    imports.extend(parsed.imports)
                    calls.extend(parsed.calls)
                    routes.extend(parsed.routes)
            elif sf.language in ("javascript", "typescript") and ts_mod.available():
                for sym in ts_mod.parse_tree_sitter(sf):
                    symbols.append(sym)
                syms, imps, rts, cls = heuristic_parser.parse_heuristic(sf)
                imports.extend(imps)
                routes.extend(rts)
            elif sf.language in ("javascript", "typescript", "go", "java", "rb", "rust",
                                 "c", "cpp", "csharp", "php"):
                syms, imps, rts, cls = heuristic_parser.parse_heuristic(sf)
                symbols.extend(syms)
                imports.extend(imps)
                routes.extend(rts)

        graph = CodeGraph(files, symbols, imports, calls, routes)
        security = scan_files(files)
        index = build_index(graph, self.settings,
                            persist_path=os.path.join(self.settings.index_dir, repo_id))
        repo = LoadedRepo(
            repo_id=repo_id, name=name or repo_id, source=source, root=root,
            summary=summary, graph=graph, security=security,
            retriever=Retriever(graph, index, top_k=self.settings.retrieval_top_k),
        )
        self._repos[repo_id] = repo
        self.registry[repo_id] = {
            "repo_id": repo_id, "name": repo.name, "source": source, "root": root,
            "indexed_at": repo.indexed_at, "ingest_seconds": round(time.time() - t0, 2),
            "files": summary.file_count, "symbols": len(symbols),
            "security_findings": len(security.findings),
        }
        self._save_registry()
        log.info("ingested %s: %d files, %d symbols, %.1fs", repo_id, len(files),
                 len(symbols), time.time() - t0)
        return repo

    def get(self, repo_id: str) -> LoadedRepo | None:
        repo = self._repos.get(repo_id)
        if repo:
            return repo
        meta = self.registry.get(repo_id)
        if not meta:
            return None
        return self.ingest(meta["source"], repo_id=repo_id, name=meta.get("name"))

    def list_repos(self) -> list[dict]:
        out = []
        for repo_id, meta in self.registry.items():
            entry = dict(meta)
            entry["loaded"] = repo_id in self._repos
            out.append(entry)
        return out

    def demo_repo(self) -> LoadedRepo:
        return self.ingest(self.settings.demo_repo_path, repo_id="ecommerce-api",
                           name="ecommerce-api")

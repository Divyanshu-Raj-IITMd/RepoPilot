"""CodeGraph: dependency graph over symbols, files and routes.

Built once per repository. Powers:
  * call-chain tracing (endpoint -> handler -> service -> data access)
  * callers/callees of a symbol
  * file-level dependency edges and transitive impact analysis
  * mapping source files to the tests that cover them
"""

from __future__ import annotations

from collections import defaultdict, deque

from app.parsing.models import CallEdge, ImportRecord, RouteInfo, SourceFile, Symbol


def module_of(path: str) -> str:
    """app/services/users.py -> app.services.users (drops __init__)."""
    p = path[:-3] if path.endswith(".py") else path
    if p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    return p.replace("/", ".")


class CodeGraph:
    def __init__(
        self,
        files: list[SourceFile],
        symbols: list[Symbol],
        imports: list[ImportRecord],
        calls: list[CallEdge],
        routes: list[RouteInfo],
    ) -> None:
        self.files = {f.path: f for f in files}
        self.symbols = symbols
        self.imports = imports
        self.raw_calls = calls
        self.routes = routes

        self.symbols_by_file: dict[str, list[Symbol]] = defaultdict(list)
        self.symbols_by_name: dict[str, list[Symbol]] = defaultdict(list)
        self.qualified_index: dict[tuple[str, str], Symbol] = {}
        for s in symbols:
            self.symbols_by_file[s.file].append(s)
            self.symbols_by_name[s.name].append(s)
            self.qualified_index[(s.file, s.qualified)] = s

        self.module_to_file: dict[str, str] = {}
        for f in files:
            if f.language == "python":
                self.module_to_file[module_of(f.path)] = f.path

        # file -> files that import it (dependents)
        self.file_dependents: dict[str, set[str]] = defaultdict(set)
        # file -> files it imports (dependencies)
        self.file_dependencies: dict[str, set[str]] = defaultdict(set)
        # alias resolution per file: local name -> (file, symbol_name|None)
        self.aliases: dict[str, dict[str, tuple[str, str | None]]] = defaultdict(dict)
        self._resolve_imports()

        self.call_edges: list[CallEdge] = []
        self.callees_of: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
        self.callers_of: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
        self._resolve_calls()

    # ------------------------------------------------------------------ imports

    def _resolve_imports(self) -> None:
        for rec in self.imports:
            base_file = self._resolve_module(rec)
            # `from pkg import submodule` — prefer the submodule file over pkg/__init__.py
            resolved = base_file
            if base_file and base_file.endswith("__init__.py") and len(rec.alias) == 1:
                only = next(iter(rec.alias.values()))
                sub = self.module_to_file.get(f"{rec.module}.{only}" if rec.module else only)
                if sub:
                    resolved = sub
            rec.resolved_file = resolved
            rec.external = resolved is None
            if resolved:
                self.file_dependencies[rec.file].add(resolved)
                self.file_dependents[resolved].add(rec.file)
            for local, original in rec.alias.items():
                target = None
                cand = None
                if base_file:
                    cand = self.module_to_file.get(
                        f"{rec.module}.{original}" if rec.module else original)
                    target = cand or base_file
                if cand and cand != resolved:
                    # per-name submodule edge: `from pkg import a, b` -> a.py, b.py
                    self.file_dependencies[rec.file].add(cand)
                    self.file_dependents[cand].add(rec.file)
                if target and target != base_file:
                    self.aliases[rec.file][local] = (target, None)
                elif resolved:
                    self.aliases[rec.file][local] = (resolved, original if original != "*" else None)
                else:
                    self.aliases[rec.file][local] = (None, original)

    def _resolve_module(self, rec: ImportRecord) -> str | None:
        """Resolve an import record to an in-repo file, None if external."""
        base = rec.module or ""
        if rec.level and rec.file.endswith(".py"):
            # relative import: walk up `level` packages from the importer
            parts = rec.file.split("/")[:-1]
            base_parts = base.split(".") if base else []
            full = parts[: len(parts) - (rec.level - 1)] + base_parts if len(parts) >= rec.level - 1 else []
            cand = ".".join(full)
            return self._module_candidates(cand)
        for cand in (base,):
            hit = self._module_candidates(cand)
            if hit:
                return hit
        return None

    def _module_candidates(self, dotted: str) -> str | None:
        if not dotted:
            return None
        if dotted in self.module_to_file:
            return self.module_to_file[dotted]
        # from app.services import users  ->  try app.services.users
        pkg = self.module_to_file.get(dotted.replace("-", "_"))
        return pkg

    # -------------------------------------------------------------------- calls

    def _resolve_calls(self) -> None:
        for edge in self.raw_calls:
            target = self._resolve_callee(edge.caller_file, edge.callee_text)
            if target is not None:
                edge.callee_file, edge.callee_symbol = target
                self.call_edges.append(edge)
                caller = (edge.caller_file, edge.caller_symbol)
                callee = target
                self.callees_of[caller].add(callee)
                self.callers_of[callee].add(caller)

    def _resolve_callee(self, caller_file: str, text: str) -> tuple[str, str] | None:
        """Resolve `user_service.get_user_by_username` / `get_user` to (file, symbol)."""
        text = text.strip()
        if text.startswith(("self.", "cls.")):
            sym = self.qualified_index.get((caller_file, text.split(".", 1)[1]))
            if sym:
                return (caller_file, sym.qualified)
            return None
        if "." in text:
            head, rest = text.split(".", 1)
            alias = self.aliases.get(caller_file, {}).get(head)
            if alias and alias[0]:
                f, orig = alias
                sym = self._find_symbol(f, orig or rest)
                if sym:
                    return (f, sym.qualified)
                # module alias: user_service.get_user -> services/users.py, name get_user
                sym = self._find_symbol(f, rest)
                if sym:
                    return (f, sym.qualified)
                # alias bound to a name imported *from* a package: try pkg.name as submodule
                if orig:
                    base_module = module_of(f)
                    sub = self.module_to_file.get(f"{base_module}.{orig}")
                    if sub:
                        sym = self._find_symbol(sub, rest)
                        if sym:
                            return (sub, sym.qualified)
            return None
        # plain name: same file first, then imports, then unique repo-wide
        sym = self._find_symbol(caller_file, text)
        if sym:
            return (caller_file, sym.qualified)
        alias = self.aliases.get(caller_file, {}).get(text)
        if alias and alias[0] and alias[1]:
            sym = self._find_symbol(alias[0], alias[1])
            if sym:
                return (alias[0], sym.qualified)
        candidates = self.symbols_by_name.get(text, [])
        if len(candidates) == 1:
            return (candidates[0].file, candidates[0].qualified)
        return None

    def _find_symbol(self, file: str, name: str) -> Symbol | None:
        sym = self.qualified_index.get((file, name))
        if sym:
            return sym
        for s in self.symbols_by_file.get(file, []):
            if s.name == name:
                return s
        return None

    # ----------------------------------------------------------------- queries

    def find_symbol(self, name: str) -> list[Symbol]:
        """Case-insensitive-ish lookup by bare or qualified name."""
        name = name.strip()
        hits = [s for s in self.symbols if s.qualified == name or s.name == name]
        if hits:
            return hits
        low = name.lower()
        return [s for s in self.symbols if s.name.lower() == low or s.qualified.lower() == low]

    def get_symbol(self, file: str, qualified: str) -> Symbol | None:
        return self.qualified_index.get((file, qualified))

    def callers(self, file: str, qualified: str) -> list[tuple[str, str]]:
        return sorted(self.callers_of.get((file, qualified), set()))

    def callees(self, file: str, qualified: str) -> list[tuple[str, str]]:
        return sorted(self.callees_of.get((file, qualified), set()))

    def find_route(self, path_hint: str, method: str | None = None) -> RouteInfo | None:
        """Find a route whose path contains the hint (e.g. '/api/users').

        When `method` is given (GET/POST/...), prefer the route with that verb.
        """
        hint = path_hint.strip().rstrip("/")
        exact = [r for r in self.routes if r.path == hint or r.path.rstrip("/") == hint]
        if not exact:
            exact = sorted(
                (r for r in self.routes if hint in r.path or r.path in hint),
                key=lambda r: -len(r.path),
            )
        if not exact:
            return None
        if method:
            method = method.upper()
            for r in exact:
                if r.method == method:
                    return r
        return exact[0]

    def trace_route(self, path_hint: str, max_depth: int = 5,
                    method: str | None = None) -> dict:
        """BFS the call graph from the handler of a route. Returns chain + files."""
        route = self.find_route(path_hint, method=method)
        if route is None:
            return {"route": None, "chain": [], "files": []}
        handler = self.qualified_index.get((route.file, route.handler))
        chain: list[dict] = [{
            "depth": 0, "symbol": route.handler, "file": route.file,
            "line": handler.start_line if handler else route.line,
            "signature": handler.signature if handler else "",
        }]
        seen = {(route.file, route.handler)}
        files = [route.file]
        frontier = deque([((route.file, route.handler), 0)])
        while frontier:
            (key, depth) = frontier.popleft()
            if depth >= max_depth:
                continue
            for callee in sorted(self.callees_of.get(key, set())):
                if callee in seen:
                    continue
                seen.add(callee)
                sym = self.qualified_index.get(callee)
                chain.append({
                    "depth": depth + 1, "symbol": callee[1], "file": callee[0],
                    "line": sym.start_line if sym else 0,
                    "signature": sym.signature if sym else "",
                })
                files.append(callee[0])
                frontier.append((callee, depth + 1))
        uniq_files = list(dict.fromkeys(files))
        return {"route": route, "chain": chain, "files": uniq_files}

    def impact(self, file: str) -> list[str]:
        """Transitive reverse dependencies: what breaks if `file` changes."""
        seen: set[str] = set()
        queue = deque([file])
        while queue:
            cur = queue.popleft()
            for dep in self.file_dependents.get(cur, set()):
                if dep not in seen:
                    seen.add(dep)
                    queue.append(dep)
        return sorted(seen)

    def tests_for_files(self, files: list[str]) -> list[str]:
        """Test files that import or textually reference any of the given files."""
        targets = set(files)
        target_modules = {module_of(f) for f in files}
        target_names = set()
        for f in files:
            for s in self.symbols_by_file.get(f, []):
                target_names.add(s.name)
        found: set[str] = set()
        for path, sf in self.files.items():
            if path in targets:
                continue  # never report the target file itself as its own test
            if not (path.rsplit("/", 1)[-1].startswith("test_")
                    or "/tests/" in f"/{path}" or "__tests__" in path):
                continue
            for rec in self.imports:
                if rec.file == path and (
                    rec.resolved_file in targets or (rec.module in target_modules)
                ):
                    found.add(path)
                    break
            if path not in found and any(n in sf.content for n in target_names if len(n) > 4):
                found.add(path)
        return sorted(found)

    def file_summary(self, file: str) -> str:
        sf = self.files.get(file)
        if not sf:
            return ""
        syms = self.symbols_by_file.get(file, [])
        parts = [f"{s.kind} {s.qualified}" for s in syms[:20]]
        return f"{file}: " + ", ".join(parts) if parts else file

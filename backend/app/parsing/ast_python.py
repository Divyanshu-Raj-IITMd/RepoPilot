"""AST-based Python parser: symbols, imports, call edges and route decorators."""

from __future__ import annotations

import ast
import re

from app.parsing.models import CallEdge, ImportRecord, RouteInfo, SourceFile, Symbol

_ROUTE_DECORATOR_RE = re.compile(
    r"^(\w+)\.(get|post|put|delete|patch|head|options)\(\s*[\"']([^\"']+)[\"']"
)


def _format_signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        args_src = ast.unparse(node.args)
    except Exception:
        args_src = ", ".join(a.arg for a in node.args.args)
    ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    return f"{prefix} {node.name}({args_src}){ret}"


def _decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    out = []
    for d in node.decorator_list:
        try:
            out.append(ast.unparse(d))
        except Exception:
            pass
    return out


def _has_explicit_return_none(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Return):
            if sub.value is None:  # bare `return`
                return True
            if isinstance(sub.value, ast.Constant) and sub.value.value is None:
                return True  # `return None`
    return False


def _raises(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    out = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Raise) and sub.exc is not None:
            try:
                src = ast.unparse(sub.exc)
                name = src.split("(")[0].strip()
                if name and name not in out:
                    out.append(name)
            except Exception:
                pass
    return out[:8]


class ParsedPythonFile:
    """Result of parsing one Python file."""

    def __init__(self, sf: SourceFile) -> None:
        self.file = sf
        self.symbols: list[Symbol] = []
        self.imports: list[ImportRecord] = []
        self.calls: list[CallEdge] = []
        self.routes: list[RouteInfo] = []
        self.ok = False
        self.error: str | None = None
        self._parse()

    def _parse(self) -> None:
        try:
            tree = ast.parse(self.file.content)
        except SyntaxError as exc:
            self.error = f"syntax error: {exc}"
            return
        self.ok = True
        self._walk_module(tree)

    def _walk_module(self, tree: ast.Module) -> None:
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                self.imports.append(self._import_record(node))
            elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self._walk_def(node, parent=None)
        # Also capture imports nested inside try/except (very common).
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)) and node not in set(
                list(getattr(tree, "body", []))
            ):
                rec = self._import_record(node)
                if not any(r.file == rec.file and r.module == rec.module for r in self.imports):
                    self.imports.append(rec)

    def _import_record(self, node: ast.Import | ast.ImportFrom) -> ImportRecord:
        if isinstance(node, ast.Import):
            rec = ImportRecord(file=self.file.path, module="", names=[], alias={})
            for alias in node.names:
                rec.names.append(alias.name)
                rec.alias[alias.asname or alias.name] = alias.name
            rec.module = ",".join(rec.names)
            return rec
        rec = ImportRecord(
            file=self.file.path,
            module=node.module or "",
            names=[a.name for a in node.names],
            alias={a.asname or a.name: a.name for a in node.names},
            level=node.level or 0,
        )
        return rec

    def _walk_def(self, node, parent: str | None) -> None:
        if isinstance(node, ast.ClassDef):
            sym = Symbol(
                name=node.name, kind="class", file=self.file.path,
                start_line=node.lineno, end_line=node.end_lineno or node.lineno,
                signature=f"class {node.name}", parent=parent,
                docstring=ast.get_docstring(node) or "",
            )
            self.symbols.append(sym)
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._walk_def(child, parent=node.name)
            return

        decorators = _decorators(node)
        sym = Symbol(
            name=node.name, kind="method" if parent else "function",
            file=self.file.path, start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            signature=_format_signature(node), docstring=ast.get_docstring(node) or "",
            parent=parent, decorators=decorators,
            returns_none=_has_explicit_return_none(node), raises=_raises(node),
        )
        self.symbols.append(sym)
        for dec in decorators:
            m = _ROUTE_DECORATOR_RE.match(dec)
            if m:
                obj, verb, path = m.groups()
                self.routes.append(RouteInfo(
                    method=verb.upper(), path=path, handler=node.name,
                    file=self.file.path, line=node.lineno,
                    framework="FastAPI" if obj in ("app", "router", "api_router", "blueprint") or obj.endswith("router") else "unknown",
                ))
        self._collect_calls(node, sym)

    def _collect_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef, sym: Symbol) -> None:
        caller = sym.qualified
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                try:
                    text = ast.unparse(sub.func)
                except Exception:
                    continue
                if len(text) < 80:
                    self.calls.append(CallEdge(
                        caller_file=self.file.path, caller_symbol=caller,
                        callee_text=text, line=sub.lineno,
                    ))


def parse_python(sf: SourceFile) -> ParsedPythonFile:
    return ParsedPythonFile(sf)

"""Heuristic regex-based parser for JS/TS/Go/Java and other languages.

Used when no Tree-sitter grammar is available. It extracts a best-effort
subset of symbols/imports/routes. The optional Tree-sitter module
(`app.parsing.treesitter`) upgrades JS/TS parsing when installed.
"""

from __future__ import annotations

import re

from app.parsing.models import CallEdge, ImportRecord, RouteInfo, SourceFile, Symbol

_FUNC_PATTERNS = [
    re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)"),
    re.compile(r"^\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)"),
    re.compile(r"^\s*(?:export\s+)?class\s+(\w+)"),
]
_METHOD_PATTERN = re.compile(r"^\s+(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*\{")
_IMPORT_PATTERNS = [
    re.compile(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"import\s+['\"]([^'\"]+)['\"]"),
    re.compile(r"const\s+\w+\s*=\s*require\(['\"]([^'\"]+)['\"]\)"),
    re.compile(r"^\s*import\s+" r"(\w[\w.]*)"),
]
_EXPRESS_ROUTE = re.compile(
    r"\b(\w+)\.(get|post|put|delete|patch)\(\s*['\"]([^'\"]+)['\"]\s*,\s*(?:.*?,\s*)?(\w+)\s*\)"
)
_GO_FUNC = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*\(")


def parse_heuristic(sf: SourceFile) -> tuple[list[Symbol], list[ImportRecord], list[RouteInfo], list[CallEdge]]:
    symbols: list[Symbol] = []
    imports: list[ImportRecord] = []
    routes: list[RouteInfo] = []
    calls: list[CallEdge] = []
    lines = sf.content.splitlines()
    lang = sf.language
    class_name = None

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if lang in ("javascript", "typescript"):
            for pat in _FUNC_PATTERNS:
                m = pat.match(line)
                if m:
                    name = m.group(1)
                    if pat.pattern.startswith(r"^\s*(?:export\s+)?class"):
                        class_name = name
                        symbols.append(Symbol(name, "class", sf.path, idx, min(idx, len(lines)),
                                              signature=f"class {name}"))
                    else:
                        params = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
                        symbols.append(Symbol(name, "method" if class_name else "function",
                                              sf.path, idx, min(idx + 4, len(lines)),
                                              signature=f"function {name}({params})"))
                    break
            for pat in _IMPORT_PATTERNS:
                m = pat.match(line)
                if m:
                    module = m.group(1)
                    imports.append(ImportRecord(file=sf.path, module=module,
                                                names=[module.rsplit("/", 1)[-1]]))
                    break
            for m in _EXPRESS_ROUTE.finditer(line):
                obj, verb, path, handler = m.groups()
                if obj in ("app", "router", "server", "api"):
                    routes.append(RouteInfo(method=verb.upper(), path=path, handler=handler,
                                            file=sf.path, line=idx, framework="Express"))
        elif lang == "go":
            m = _GO_FUNC.match(line)
            if m:
                symbols.append(Symbol(m.group(1), "function", sf.path, idx,
                                      min(idx + 3, len(lines)), signature=line.strip()[:100]))
            m = re.match(r'^\s*"([^"]+)"$', stripped)
            if m and imports and imports[-1].module == "__go_imports__":
                imports.append(ImportRecord(file=sf.path, module=m.group(1), names=[]))
            if stripped == "import (":
                imports.append(ImportRecord(file=sf.path, module="__go_imports__", names=[]))
        else:
            # Generic fallback: function-ish definitions in C-family languages.
            m = re.match(r"^\s*(?:public|private|protected|static|final|async|\s)*"
                         r"[\w<>[\]]+\s+(\w+)\s*\([^;]*\)\s*\{?\s*$", line)
            if m and m.group(1) not in ("if", "for", "while", "switch", "catch", "return"):
                symbols.append(Symbol(m.group(1), "function", sf.path, idx,
                                      min(idx + 3, len(lines)), signature=stripped[:100]))

    # Drop the sentinel used for Go import blocks.
    imports = [i for i in imports if i.module != "__go_imports__"]
    return symbols, imports, routes, calls

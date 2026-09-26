"""Optional Tree-sitter upgrade for JS/TS parsing.

RepoPilot works out of the box with `ast` (Python) and a heuristic parser
(JS/TS/Go/...). Installing the optional extras

    pip install tree-sitter tree-sitter-javascript tree-sitter-typescript

upgrades JavaScript/TypeScript symbol extraction to real AST parsing.
This module degrades gracefully: ``available()`` reports whether the
grammars are importable, and the indexer falls back to the heuristic
parser otherwise.
"""

from __future__ import annotations

from app.parsing.models import SourceFile, Symbol

_AVAILABLE: bool | None = None
_LANGS: dict[str, object] = {}


def available() -> bool:
    global _AVAILABLE, _LANGS
    if _AVAILABLE is not None:
        return _AVAILABLE
    try:  # pragma: no cover - depends on optional deps
        import tree_sitter
        import tree_sitter_javascript
        import tree_sitter_typescript

        _LANGS["javascript"] = tree_sitter.Language(tree_sitter_javascript.language())
        _LANGS["typescript"] = tree_sitter.Language(tree_sitter_typescript.language_typescript())
        _AVAILABLE = True
    except Exception:
        _AVAILABLE = False
    return _AVAILABLE


def parse_tree_sitter(sf: SourceFile) -> list[Symbol]:
    """Parse a JS/TS file with Tree-sitter, returning symbols."""
    if not available() or sf.language not in _LANGS:  # pragma: no cover
        return []
    import tree_sitter

    lang = _LANGS[sf.language]
    parser = tree_sitter.Parser(lang)
    tree = parser.parse(sf.content.encode("utf-8"))
    symbols: list[Symbol] = []
    lines = sf.content.splitlines()

    def walk(node, class_ctx=None):
        if node.type in ("function_declaration", "method_definition", "function_specifier"):
            name_node = node.child_by_field_name("name")
            if name_node is not None:
                name = sf.content[name_node.start_byte:name_node.end_byte]
                kind = "method" if class_ctx else "function"
                sig_line = lines[node.start_point[0]][:120] if lines else ""
                symbols.append(Symbol(name, kind, sf.path,
                                      node.start_point[0] + 1, node.end_point[0] + 1,
                                      signature=sig_line.strip(), parent=class_ctx))
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            cname = sf.content[name_node.start_byte:name_node.end_byte] if name_node else None
            if cname:
                symbols.append(Symbol(cname, "class", sf.path,
                                      node.start_point[0] + 1, node.end_point[0] + 1,
                                      signature=f"class {cname}"))
            for child in node.children:
                walk(child, cname or class_ctx)
            return
        for child in node.children:
            walk(child, class_ctx)

    walk(tree.root_node)
    return symbols

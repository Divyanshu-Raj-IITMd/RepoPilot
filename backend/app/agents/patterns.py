"""Deterministic static risk-pattern detectors shared by the Issue Investigator
and the PR Reviewer. These produce real findings with file:line evidence.

Philosophy: the *pipeline* finds the facts; the LLM (when present) only
explains them. Findings are therefore reproducible and testable.
"""

from __future__ import annotations

import ast
import re

from app.agents.findings import Finding
from app.graph.code_graph import CodeGraph

# --------------------------------------------------------------------- patterns

SQL_STRING_BUILD = re.compile(
    r"(?:execute|executemany|query_all|query_one|cursor\.\w+)\s*\(\s*f[\"']"
    r"|(?:execute|executemany)\s*\(\s*[\"'][^\"']*(?:SELECT|INSERT|UPDATE|DELETE)[^\"']*['\"]\s*\+"
    r"|\bformat\(\s*[\"'](?:SELECT|INSERT|UPDATE|DELETE)",
    re.I,
)
SQL_FSTRING_ANYWHERE = re.compile(r"f[\"'][^\"']*(?:SELECT |INSERT |UPDATE |DELETE )", re.I)
BARE_EXCEPT = re.compile(r"except\s*(?:Exception|BaseException)?\s*(?:as\s+\w+)?\s*:\s*(?:pass|\.\.\.)")
DANGEROUS_CALL = re.compile(r"\b(?:eval|exec)\s*\(|\bos\.system\s*\(|subprocess\.\w+\([^)]*shell\s*=\s*True")
WEAK_HASH_FOR_PASSWORD = re.compile(r"hashlib\.(?:md5|sha1)\s*\(")
MUTABLE_DEFAULT = re.compile(r"def\s+\w+\s*\([^)]*=\s*(?:\[\]|\{\})")
EQ_NONE = re.compile(r"==\s*None|!=\s*None")
TODO_FIXME = re.compile(r"\b(?:TODO|FIXME|XXX|HACK)\b")
AUTH_MARKER = re.compile(r"auth|Depends\(|@requires|get_current_user|verify_token|login_required", re.I)
EXEC_IN_LOOP = re.compile(r"\bfor\b.*:\s*$")


def find_none_deref(graph: CodeGraph, files: list[str]) -> list[Finding]:
    """Detect `x = <may_return_none_call>()` followed by unchecked `x[...]`/`x.attr`.

    "May return None" = a resolved call target whose symbol explicitly returns
    None (tracked by the Python AST parser), or a name starting with get_/find_/
    fetch_/query_ in a data-access context.
    """
    findings: list[Finding] = []
    for file in files:
        sf = graph.files.get(file)
        if not sf or sf.language != "python":
            continue
        lines = sf.content.splitlines()
        for sym in graph.symbols_by_file.get(file, []):
            if sym.kind == "class":
                continue
            body = lines[sym.start_line - 1: sym.end_line]
            assigned: list[tuple[str, int, str]] = []
            for i, line in enumerate(body):
                m = re.match(r"\s*(\w+)\s*=\s*(.+)$", line)
                if not m:
                    continue
                var, rhs = m.groups()
                call = re.match(r"[\w.]*?(get_|find_|fetch_|query_)\w+\s*\(", rhs)
                if call:
                    assigned.append((var, sym.start_line + i, rhs.strip()[:100]))
            for var, assign_line, rhs in assigned:
                guard = re.compile(rf"if\s+(?:not\s+)?{var}\b|{var}\s+is\s+(?:not\s+)?None")
                for j, line in enumerate(body):
                    lineno = sym.start_line + j
                    if lineno <= assign_line:
                        continue
                    if guard.search(line):
                        break
                    usage = re.search(rf"\b{var}(?:\[[\'\"\w]|\.\w)", line)
                    if usage:
                        findings.append(Finding(
                            severity="HIGH", category="unhandled_none",
                            title=f"Possible None dereference: `{var}` is used without a None check",
                            file=file, line=lineno, snippet=line.strip()[:160],
                            rationale=(
                                f"`{var}` is assigned from `{rhs}` which can return None "
                                f"(assignment at line {assign_line}); line {lineno} then uses "
                                f"`{var}` directly, which raises TypeError/AttributeError when None."
                            ),
                        ))
                        break
    return findings


def find_sql_injection(graph: CodeGraph, files: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for file in files:
        sf = graph.files.get(file)
        if not sf:
            continue
        for i, line in enumerate(sf.content.splitlines(), start=1):
            interpolated = re.findall(r"\{(\w+)\}", line)
            all_constants = interpolated and all(v.isupper() for v in interpolated)
            if interpolated:
                flag = not all_constants and bool(
                    SQL_STRING_BUILD.search(line) or SQL_FSTRING_ANYWHERE.search(line))
            else:
                # no braces: concatenation / .format() variants
                flag = bool(SQL_STRING_BUILD.search(line))
            if flag:
                findings.append(Finding(
                    severity="HIGH", category="sql_injection",
                    title="SQL built via string interpolation (injection risk)",
                    file=file, line=i, snippet=line.strip()[:160],
                    rationale="User-controlled values interpolated directly into SQL text "
                              "instead of bound parameters (? placeholders).",
                ))
    return findings


def find_swallowed_errors(graph: CodeGraph, files: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for file in files:
        sf = graph.files.get(file)
        if not sf:
            continue
        for i, line in enumerate(sf.content.splitlines(), start=1):
            if BARE_EXCEPT.search(line):
                findings.append(Finding(
                    severity="MEDIUM", category="swallowed_error",
                    title="Broad except swallows the error",
                    file=file, line=i, snippet=line.strip()[:160],
                    rationale="`except: pass` hides failures and turns bugs into silent "
                              "wrong behaviour.",
                ))
    return findings


def find_dangerous_calls(graph: CodeGraph, files: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for file in files:
        sf = graph.files.get(file)
        if not sf:
            continue
        for i, line in enumerate(sf.content.splitlines(), start=1):
            if DANGEROUS_CALL.search(line):
                findings.append(Finding(
                    severity="HIGH", category="dangerous_call",
                    title="Dangerous call (eval/exec/shell)",
                    file=file, line=i, snippet=line.strip()[:160],
                    rationale="eval/exec/os.system/shell=True execute attacker-influenceable "
                              "strings.",
                ))
    return findings


def find_misc_quality(graph: CodeGraph, files: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for file in files:
        sf = graph.files.get(file)
        if not sf:
            continue
        for i, line in enumerate(sf.content.splitlines(), start=1):
            if MUTABLE_DEFAULT.search(line):
                findings.append(Finding(
                    severity="MEDIUM", category="mutable_default",
                    title="Mutable default argument", file=file, line=i,
                    snippet=line.strip()[:160],
                    rationale="Mutable defaults ([]/{}) are shared across calls — a classic "
                              "Python bug source.",
                ))
            elif EQ_NONE.search(line):
                findings.append(Finding(
                    severity="LOW", category="style",
                    title="Comparison to None should use `is`", file=file, line=i,
                    snippet=line.strip()[:160], rationale="PEP 8: use `is None` / `is not None`.",
                ))
            elif WEAK_HASH_FOR_PASSWORD.search(line) and "password" in sf.content.lower():
                findings.append(Finding(
                    severity="MEDIUM", category="weak_crypto",
                    title="Weak hash used in a password context", file=file, line=i,
                    snippet=line.strip()[:160],
                    rationale="MD5/SHA1 are not password hashing functions; use "
                              "bcrypt/scrypt/argon2 with a salt.",
                ))
            elif TODO_FIXME.search(line):
                findings.append(Finding(
                    severity="LOW", category="todo",
                    title="TODO/FIXME marker left in code", file=file, line=i,
                    snippet=line.strip()[:160],
                    rationale="Unfinished work tracked in a comment.",
                ))
    return findings


def find_missing_error_handling(graph: CodeGraph, files: list[str]) -> list[Finding]:
    """HTTP handlers with no try/except and no exception_handler route."""
    findings: list[Finding] = []
    for route in graph.routes:
        if route.file not in files:
            continue
        sym = graph.get_symbol(route.file, route.handler)
        if not sym:
            continue
        sf = graph.files.get(route.file)
        body = sf.content.splitlines()[sym.start_line - 1: sym.end_line] if sf else []
        if not any(re.search(r"\btry\s*:|except\b|raise HTTPException", ln) for ln in body):
            findings.append(Finding(
                severity="MEDIUM", category="missing_error_handling",
                title=f"{route.method} {route.path}: handler has no error handling",
                file=route.file, line=sym.start_line,
                snippet=sym.signature,
                rationale="Any exception from the service/data layers escapes as a raw "
                          "HTTP 500 instead of a precise status code.",
            ))
    return findings


def find_n_plus_one(graph: CodeGraph, files: list[str]) -> list[Finding]:
    """A loop body issuing per-iteration DB writes/queries."""
    findings: list[Finding] = []
    for file in files:
        sf = graph.files.get(file)
        if not sf or sf.language != "python":
            continue
        lines = sf.content.splitlines()
        for sym in graph.symbols_by_file.get(file, []):
            if sym.kind == "class":
                continue
            body = lines[sym.start_line - 1: sym.end_line]
            in_loop = 0
            for k, line in enumerate(body):
                if re.match(r"\s*for\s+\w+.*:", line):
                    in_loop = 3
                elif in_loop and re.match(r"\s*\w", line) and not re.match(r"\s{4,}", line):
                    in_loop = 0
                if in_loop and re.search(r"\b(?:db|cursor)\.(?:execute|query_all|query_one)\s*\(", line):
                    findings.append(Finding(
                        severity="MEDIUM", category="n_plus_one",
                        title="Query executed inside a loop (N+1 pattern)",
                        file=file, line=sym.start_line + k,
                        snippet=line.strip()[:160],
                        rationale="One DB round-trip per item; batch the inserts/queries "
                                  "instead.",
                    ))
                    in_loop = 0
    return findings


def find_unvalidated_rates(graph: CodeGraph, files: list[str]) -> list[Finding]:
    """Rate-like parameters (discount/rate/percent/...) used without a range guard."""
    findings: list[Finding] = []
    rate_re = re.compile(r"^(?:discount|rate|ratio|percent(?:age)?|commission|fee|tax)$", re.I)
    for file in files:
        sf = graph.files.get(file)
        if not sf or sf.language != "python":
            continue
        for sym in graph.symbols_by_file.get(file, []):
            if sym.kind == "class":
                continue
            params = re.findall(r"[\(\s,](\w+)(?::\s*[\w\[\]\., ]+)?(?:\s*=\s*[^,)]+)?[,)]",
                                sym.signature)
            for p in params:
                if not rate_re.match(p):
                    continue
                body = sf.content.splitlines()[sym.start_line - 1: sym.end_line]
                guarded = any(re.search(rf"\bif\b[^\n]*\b{p}\b", ln) for ln in body)
                used = any(p in ln for ln in body[1:])
                if used and not guarded:
                    findings.append(Finding(
                        severity="MEDIUM", category="missing_validation",
                        title=f"`{p}` is used without range validation",
                        file=file, line=sym.start_line, snippet=sym.signature[:160],
                        rationale=f"`{p}` looks like a fraction (0..1) but is never guarded "
                                  f"with an `if` — values below 0 or above 1 produce "
                                  f"out-of-range results (e.g. negative totals).",
                    ))
    return findings


def find_missing_input_validation(graph: CodeGraph, files: list[str]) -> list[Finding]:
    """HTTP handlers that pass request-body fields to services unvalidated."""
    findings: list[Finding] = []
    for route in graph.routes:
        if route.file not in files:
            continue
        sym = graph.get_symbol(route.file, route.handler)
        if not sym:
            continue
        sf = graph.files.get(route.file)
        body = sf.content.splitlines()[sym.start_line - 1: sym.end_line] if sf else []
        body_src = "\n".join(body)
        accessed = set(re.findall(r"body(?:\.get\(\s*|\[)\s*[\"'](\w+)[\"']", body_src))
        if not accessed:
            continue
        validated = set()
        for line in body:
            if re.search(r"validat|assert|check_|sanitize|verify", line, re.I):
                for m in re.findall(r"[\"'](\w+)[\"']", line):
                    validated.add(m)
        unvalidated = sorted(accessed - validated)
        if unvalidated:
            findings.append(Finding(
                severity="MEDIUM", category="missing_input_validation",
                title=f"{route.method} {route.path}: field(s) used without validation: "
                      f"{', '.join(unvalidated)}",
                file=route.file, line=sym.start_line, snippet=sym.signature[:160],
                rationale="Request-body fields reach the service layer without any "
                          "validate_/assert/check call — malformed input propagates "
                          "downstream (or causes 500s).",
            ))
    return findings


def find_dead_stores(graph: CodeGraph, files: list[str]) -> list[Finding]:
    """Accumulated local variables that are never read afterwards.

    Catches the classic "computed it twice, wired up the wrong one" bug:
    a value is built up inside a loop (`total += ...`) but the value that
    is actually returned/used comes from somewhere else. When the used
    value originates from a call, that call is named in the rationale so
    the answer points at the redundant computation explicitly.
    """
    findings: list[Finding] = []
    for file in files:
        sf = graph.files.get(file)
        if not sf or sf.language != "python":
            continue
        try:
            tree = ast.parse(sf.content)
        except SyntaxError:
            continue
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            loads = {n.id for n in ast.walk(fn)
                     if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
            calls_assigned: dict[str, str] = {}
            for n in ast.walk(fn):
                if (isinstance(n, ast.Assign) and len(n.targets) == 1
                        and isinstance(n.targets[0], ast.Name)
                        and isinstance(n.value, ast.Call)
                        and isinstance(n.value.func, ast.Name)):
                    calls_assigned[n.targets[0].id] = n.value.func.id
            for n in ast.walk(fn):
                if (isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name)):
                    var = n.target.id
                    if var.startswith("_") or var in loads:
                        continue
                    used_call = ""
                    for ret in ast.walk(fn):
                        if isinstance(ret, ast.Return) and ret.value is not None:
                            for rn in ast.walk(ret.value):
                                if (isinstance(rn, ast.Name) and rn.id in calls_assigned):
                                    used_call = calls_assigned[rn.id]
                    via = (f"the value actually returned is computed by "
                           f"`{used_call}(...)` instead — ") if used_call else ""
                    findings.append(Finding(
                        severity="MEDIUM", category="dead_store",
                        title=f"`{var}` is computed but never used",
                        file=file, line=n.lineno,
                        snippet=sf.content.splitlines()[n.lineno - 1].strip()[:160],
                        rationale=f"`{var}` is accumulated inside a loop in {fn.name}() but "
                                  f"never read afterwards; {via}one of the two computations "
                                  f"is redundant or the wrong one was wired up.",
                    ))
    return findings


ALL_CHECKS = {
    "sql_injection": find_sql_injection,
    "unhandled_none": find_none_deref,
    "swallowed_error": find_swallowed_errors,
    "dangerous_call": find_dangerous_calls,
    "missing_error_handling": find_missing_error_handling,
    "missing_input_validation": find_missing_input_validation,
    "missing_validation": find_unvalidated_rates,
    "n_plus_one": find_n_plus_one,
    "dead_store": find_dead_stores,
    "quality": find_misc_quality,
}


def run_all_checks(graph: CodeGraph, files: list[str],
                   categories: list[str] | None = None) -> list[Finding]:
    out: list[Finding] = []
    for name, fn in ALL_CHECKS.items():
        if categories and name not in categories:
            continue
        try:
            out.extend(fn(graph, files))
        except Exception:
            continue
    return out

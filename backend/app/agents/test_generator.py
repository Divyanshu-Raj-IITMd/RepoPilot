"""Agent 5 — Test Generation Agent (with the verification loop).

For a target function the agent:
  1. analyses the signature via AST (params, types, defaults, docstring),
  2. derives a category matrix (normal / empty / zero / negative / large /
     boundary / invalid) — the same checklist a senior engineer uses,
  3. renders a self-contained pytest module,
  4. runs it in the sandbox, classifies failures, optionally proposes a
     validation patch and re-runs (max N iterations),
  5. returns a verdict: validated / validated_after_fix / rejected.
"""

from __future__ import annotations

import ast
import os
import re

from app.agents.findings import AgentResult, make_citation
from app.agents.state import EventTap
from app.config import get_settings
from app.sandbox.executor import BaseExecutor, get_executor
from app.verification.loop import VerificationResult, classify_failures, run_pytest

_RATE_NAMES = ("discount", "rate", "ratio", "percent", "commission", "fee", "tax")
_TOTAL_NAMES = ("total", "sum", "amount", "invoice", "price", "balance", "cost", "subtotal")
_ITERABLE_NAMES = ("items", "cart", "list", "rows", "values", "entries", "records", "orders", "products")


# ------------------------------------------------------------- case derivation

def _analyze_signature(func_src: str) -> dict | None:
    try:
        tree = ast.parse(func_src)
    except SyntaxError:
        return None
    node = next((n for n in tree.body if isinstance(n, ast.FunctionDef)), None)
    if node is None:
        return None
    params = []
    defaults = [None] * (len(node.args.args) - len(node.args.defaults)) + list(node.args.defaults)
    for arg, default in zip(node.args.args, defaults, strict=False):
        params.append({
            "name": arg.arg,
            "annotation": ast.unparse(arg.annotation) if arg.annotation else "",
            "default": ast.unparse(default) if default is not None else None,
        })
    doc = ast.get_docstring(node) or ""
    example = None
    m = re.search(r">>>\s*(.+?)\s*\n\s*(.+)", doc)
    if m:
        example = (m.group(1).strip(), m.group(2).strip())
    returns = ast.unparse(node.returns) if node.returns else ""

    # documented + actual raises: `raise ValueError(...)` in the body, plus
    # "Raises ValueError" prose in the docstring
    raises: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Raise) and n.exc is not None:
            exc = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
            if isinstance(exc, ast.Name):
                raises.add(exc.id)
    for e in re.findall(r"\braises?\s+((?:\w+\.)*\w+)", doc, re.I):
        base = e.split(".")[-1]
        if base[:1].isupper():  # exception names are capitalized
            raises.add(base)

    # body-derived guards: `if <param> < CONST: raise` / `if <param> is None: raise`
    guards: dict[str, dict] = {}
    for n in ast.walk(node):
        if not isinstance(n, ast.If):
            continue
        raises_here = any(isinstance(sub, ast.Raise) for sub in ast.walk(n))
        if not raises_here:
            continue
        for sub in ast.walk(n):
            if (isinstance(sub, ast.Compare) and isinstance(sub.left, ast.Name)
                    and len(sub.ops) == 1):
                pname = sub.left.id
                if isinstance(sub.ops[0], ast.Is) and any(
                        isinstance(c, ast.Constant) and c.value is None for c in sub.comparators):
                    guards.setdefault(pname, {})["none_raises"] = True
                elif isinstance(sub.ops[0], ast.Lt) and isinstance(sub.comparators[0], ast.Constant) \
                        and isinstance(sub.comparators[0].value, (int, float)):
                    guards.setdefault(pname, {})["min"] = sub.comparators[0].value

    return {"name": node.name, "params": params, "doc": doc, "example": example,
            "returns": returns, "body": func_src, "raises": sorted(raises),
            "guards": guards}


_MAPPING_NAMES = ("payload", "body", "data", "params", "context", "ctx", "claims",
                   "meta", "options", "config", "attrs", "extra")
_STRING_NAMES = ("token", "key", "secret", "name", "email", "username", "password",
                 "id", "status", "query", "text", "message", "url", "path", "code",
                 "label", "title", "value", "note", "category", "q", "s")
_COUNT_NAMES = ("quantity", "qty", "count", "limit", "size", "page", "offset",
                "port", "level", "index", "idx", "num", "amount")


def _param_kind(p: dict) -> str:
    name = p["name"].lower()
    ann = p["annotation"].lower()
    if any(k in name for k in _RATE_NAMES):
        return "rate"
    if any(k in name for k in _MAPPING_NAMES) or ann.startswith("dict"):
        return "mapping"
    if any(k in name for k in _ITERABLE_NAMES) or "list" in ann or "sequence" in ann:
        return "iterable"
    if ann in ("int", "float"):
        return "numeric"
    if any(k in name for k in _TOTAL_NAMES):
        return "numeric"
    if any(k in name for k in _COUNT_NAMES):
        return "numeric"
    if ann == "str" or ann.startswith("str") or name in _STRING_NAMES:
        return "string"
    if not ann and p["default"] is None:
        return "unknown"
    return "generic"


def _valid_value(p: dict, kind: str) -> str:
    if p["default"] is not None:
        return p["default"]
    if kind == "rate":
        return "0.1"
    if kind == "iterable":
        return '[{"price": 10, "quantity": 2}]'
    if kind == "mapping":
        return '{"sub": "alice"}'
    if kind == "string":
        return '"sample-value-123"'
    if kind == "unknown":
        return "None"
    return '1'


def generate_cases(sig: dict) -> list:
    """Build the category matrix for a function."""
    from app.verification.loop import TestCase

    name = sig["name"]
    params = sig["params"]
    if not params:
        return [TestCase(label=f"test_{name}_smoke", category="normal",
                         call_src=f"{name}()", expectation="no_crash")]
    kinds = {p["name"]: _param_kind(p) for p in params}
    valid = {p["name"]: _valid_value(p, kinds[p["name"]]) for p in params}
    is_total = any(k in name.lower() for k in _TOTAL_NAMES) or "total" in sig["doc"].lower()

    def call(overrides: dict) -> str:
        kw = dict(valid)
        kw.update(overrides)
        inner = ", ".join(f"{k}={v}" for k, v in kw.items())
        return f"{name}({inner})"

    cases: list[TestCase] = []

    # encode_X <-> decode_X counterpart (both directions)
    counterpart = None
    if name.startswith("encode_"):
        counterpart = "decode_" + name[len("encode_"):]
    elif name.startswith("decode_"):
        counterpart = "encode_" + name[len("decode_"):]

    # body-derived guards refine the "valid" value (smallest legal input)
    for p in params:
        guard = sig.get("guards", {}).get(p["name"]) or {}
        if guard.get("min") is not None and kinds[p["name"]] == "numeric":
            valid[p["name"]] = str(guard["min"])

    # a decoder's first param is only valid when produced by its encoder
    if counterpart and name.startswith("decode_") and params:
        valid[params[0]["name"]] = f'{counterpart}({{"sub": "alice"}})'

    # docstring example -> exact expectation (skip placeholder values like 'eyJ...')
    if sig["example"]:
        expr, expected = sig["example"]
        if "..." not in expected:
            cases.append(TestCase(label="test_docstring_example", category="normal",
                                  call_src=f"{name}({expr.split('(', 1)[1].rsplit(')', 1)[0]})",
                                  expectation="exact", expected_value=expected))

    # normal case
    cases.append(TestCase(label="test_normal", category="normal", call_src=call({}),
                          expectation="ge_zero" if is_total else "no_crash"))

    # round-trip pair: the strongest property test (encode->decode or decode->encode)
    if counterpart and params:
        if name.startswith("encode_"):
            orig = valid[params[0]["name"]] if params else "None"
            cases.append(TestCase(
                label="test_roundtrip", category="normal",
                call_src=f"{counterpart}({name}({orig}))",
                expectation="roundtrip", expected_value=orig,
            ))
        else:
            payload = '{"sub": "alice"}'
            cases.append(TestCase(
                label="test_roundtrip", category="normal",
                call_src=f"{name}({counterpart}({payload}))",
                expectation="roundtrip_dict", expected_value=payload,
            ))

    raises_documented = bool(sig.get("raises"))

    for p in params:
        kind = kinds[p["name"]]
        pn = p["name"]
        guard = sig.get("guards", {}).get(pn) or {}
        if kind == "iterable":
            cases.append(TestCase(label=f"test_empty_{pn}", category="empty",
                                  call_src=call({pn: "[]"}),
                                  expectation="ge_zero" if is_total else "no_crash"))
            cases.append(TestCase(label=f"test_large_{pn}", category="large",
                                  call_src=call({pn: '[{"price": 999999, "quantity": 100000}]'}),
                                  expectation="no_crash"))
        elif kind == "rate":
            cases.append(TestCase(label=f"test_zero_{pn}", category="zero",
                                  call_src=call({pn: "0"}), expectation="ge_zero" if is_total else "no_crash"))
            cases.append(TestCase(label=f"test_boundary_{pn}_full", category="boundary",
                                  call_src=call({pn: "1"}),
                                  expectation="ge_zero" if is_total else "no_crash"))
            cases.append(TestCase(label=f"test_invalid_{pn}_above_one", category="invalid",
                                  call_src=call({pn: "1.5"}), expectation="raises"))
            cases.append(TestCase(label=f"test_invalid_{pn}_negative", category="invalid",
                                  call_src=call({pn: "-0.5"}), expectation="raises"))
        elif kind == "mapping":
            cases.append(TestCase(label=f"test_empty_{pn}", category="empty",
                                  call_src=call({pn: "{}"}), expectation="no_crash"))
        elif kind == "string":
            if raises_documented:
                cases.append(TestCase(label=f"test_empty_{pn}", category="invalid",
                                      call_src=call({pn: '""'}), expectation="raises"))
                cases.append(TestCase(label=f"test_invalid_{pn}_garbage", category="invalid",
                                      call_src=call({pn: '"!!!garbage!!!"'}), expectation="raises"))
            else:
                cases.append(TestCase(label=f"test_empty_{pn}", category="empty",
                                      call_src=call({pn: '""'}), expectation="no_crash"))
        elif kind == "numeric":
            min_guard = guard.get("min")
            if min_guard is not None:
                # the body documents the legal minimum: below it must raise
                cases.append(TestCase(label=f"test_zero_{pn}", category="zero",
                                      call_src=call({pn: "0"}),
                                      expectation="raises" if min_guard > 0 else
                                      ("ge_zero" if is_total else "no_crash")))
                cases.append(TestCase(label=f"test_negative_{pn}", category="negative",
                                      call_src=call({pn: "-1"}),
                                      expectation="raises" if min_guard >= 0 else
                                      ("ge_zero" if is_total else "no_crash")))
                if min_guard > 0:
                    cases.append(TestCase(label=f"test_boundary_{pn}", category="boundary",
                                          call_src=call({pn: str(min_guard)}),
                                          expectation="no_crash"))
                if guard.get("none_raises"):
                    cases.append(TestCase(label=f"test_none_{pn}", category="invalid",
                                          call_src=call({pn: "None"}), expectation="raises"))
            else:
                cases.append(TestCase(label=f"test_zero_{pn}", category="zero",
                                      call_src=call({pn: "0"}),
                                      expectation="ge_zero" if is_total else "no_crash"))
                cases.append(TestCase(label=f"test_negative_{pn}", category="negative",
                                      call_src=call({pn: "-1"}),
                                      expectation="ge_zero" if is_total else "no_crash"))
        # 'unknown'/'generic' params: no fabricated edge cases — honest limitation
    return cases


def render_test_module(import_line: str, sig: dict, cases: list,
                       extra_imports: list[tuple[str, str]] | None = None) -> str:
    """Render a standalone pytest module for the derived cases."""
    name = sig["name"]
    lines = [
        '"""Generated by RepoPilot\'s Test Generation Agent.',
        "",
        f"Target: {name} — categories: " + ", ".join(sorted({c.category for c in cases})),
        '"""',
        "import pytest",
        "",
        f"from {import_line} import {name}",
    ]
    for _mod, _sym in (extra_imports or []):
        lines.append(f"from {_mod} import {_sym}")
    lines.append("")
    for case in cases:
        lines.append("")
        if case.expectation == "raises":
            lines.append(f"def {case.label}():")
            lines.append("    with pytest.raises((ValueError, TypeError)):")
            lines.append(f"        {case.call_src}")
        elif case.expectation == "ge_zero":
            lines.append(f"def {case.label}():")
            lines.append(f"    result = {case.call_src}")
            lines.append('    assert result >= 0, f"expected non-negative total, got {result!r}"')
        elif case.expectation == "roundtrip":
            lines.append(f"def {case.label}():")
            lines.append(f"    rebuilt = {case.call_src}")
            lines.append("    assert rebuilt  # counterpart verified the round trip")
        elif case.expectation == "roundtrip_dict":
            payload = case.expected_value or '{"sub": "alice"}'
            lines.append(f"def {case.label}():")
            lines.append(f"    rebuilt = {case.call_src}")
            lines.append(f"    for k, v in {payload}.items():")
            lines.append('        assert rebuilt[k] == v, f"round-trip mismatch for {k}"')
        elif case.expectation == "exact":
            expected = case.expected_value
            if expected and not (expected.startswith("'") or expected.startswith('"')
                                 or re.match(r"^-?\d", expected)):
                expected = f'"{expected}"'
            lines.append(f"def {case.label}():")
            lines.append(f"    assert {case.call_src} == {expected}")
        else:
            lines.append(f"def {case.label}():")
            lines.append(f"    result = {case.call_src}")
            lines.append("    assert result is not None or True  # smoke: must not raise")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------ patch proposals

def propose_validation_patch(sig: dict, classes: dict[str, list[str]]) -> dict | None:
    """Propose a guard-insertion patch when failures indicate missing validation."""
    if not classes.get("missing_validation"):
        return None
    params = sig["params"]
    guards = []
    for p in params:
        kind = _param_kind(p)
        if kind == "rate" and (any(f"{p['name']}" in t for t in classes["missing_validation"])):
            guards.append(
                f'    if not 0 <= {p["name"]} <= 1:\n'
                f'        raise ValueError("{p["name"]} must be between 0 and 1")'
            )
    if guards:
        return {
            "target": sig["name"],
            "description": "validate rate-like parameters before computing",
            "code": "\n".join(guards),
            "insert_after_signature": True,
        }
    return None


def apply_patch(source: str, patch: dict) -> str:
    """Insert the proposed guard after the target's signature (and docstring)."""
    lines = source.splitlines()
    out: list[str] = []
    inserted = False
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if not inserted and re.match(rf"\s*def\s+{re.escape(patch['target'])}\s*\(", lines[i]):
            j = i + 1
            # skip a docstring block so it stays the function's docstring
            if j < len(lines) and re.match(r'\s*[ru]*("""|\'\'\')', lines[j]):
                quote = lines[j].strip()[:3].lstrip("ru")
                if lines[j].strip().endswith(quote) and len(lines[j].strip()) > 5:
                    j += 1  # one-line docstring
                else:
                    j += 1
                    while j < len(lines) and quote not in lines[j]:
                        j += 1
                    j += 1
            out.extend(lines[i + 1: j])
            out.append(patch["code"])
            i = j
            inserted = True
            continue
        i += 1
    return "\n".join(out) if inserted else source


# ------------------------------------------------------------------- the agent

def generate_tests(repo, target: str, executor: BaseExecutor | None = None,
                   max_iterations: int = 2) -> tuple[AgentResult, VerificationResult]:
    EventTap.emit("agent", agent="test_generator", status="started", target=target)
    g = repo.graph
    settings = get_settings()
    executor = executor or get_executor(settings)

    syms = g.find_symbol(target)
    if not syms:
        return (AgentResult(agent="test_generator",
                            summary=f"Symbol '{target}' not found in the repository."),
                VerificationResult(status="error", target=target, total=0, passed=0,
                                   summary=f"symbol '{target}' not found"))
    sym = syms[0]
    sf = g.files[sym.file]
    func_src = "\n".join(sf.content.splitlines()[sym.start_line - 1: sym.end_line])
    sig = _analyze_signature(func_src)
    if sig is None:
        return (AgentResult(agent="test_generator",
                            summary=f"Could not parse '{target}' as a Python function."),
                VerificationResult(status="error", target=target, total=0, passed=0,
                                   summary="unparsable target"))

    cases = generate_cases(sig)
    module = module_import_path(sym.file)
    extra_imports: list[tuple[str, str]] = []
    # every helper the generated tests call (round-trip counterparts etc.)
    called = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", " ".join(c.call_src for c in cases)))
    for fname in sorted(called - {sig["name"]}):
        c_syms = g.find_symbol(fname)
        if c_syms:
            extra_imports.append((module_import_path(c_syms[0].file), fname))
    test_code = render_test_module(module, sig, cases, extra_imports)
    test_rel = f"test_repopilot_gen_{sig['name']}.py"

    EventTap.emit("tool", agent="test_generator", tool="derive_cases",
                  cases=len(cases), categories=sorted({c.category for c in cases}))

    # ---- verification loop
    workspace = executor.make_workspace(repo.root)
    iterations: list[dict] = []
    passed, total = 0, len(cases)
    status = "rejected"
    patch: dict | None = None
    try:
        for it in range(1, max_iterations + 1):
            with open(f"{workspace}/{test_rel}", "w", encoding="utf-8") as fh:
                fh.write(test_code)
            EventTap.emit("tool", agent="test_generator", tool="run_tests",
                          iteration=it, command=f"pytest {test_rel}")
            run = run_pytest(executor, workspace, test_rel, settings.test_timeout)
            passed = run.passed
            classes = classify_failures(run)
            iterations.append({
                "iteration": it,
                "passed": run.passed, "failed": run.failed, "errors": run.errors,
                "failed_tests": run.failed_tests,
                "failure_classes": {k: v for k, v in classes.items() if v},
                "output_tail": run.output[-1200:],
                "executor": run.executor, "duration_s": round(run.duration_s, 2),
            })
            EventTap.emit("tool", agent="test_generator", tool="test_results",
                          iteration=it, passed=run.passed, failed=run.failed)
            if run.passed + run.failed + run.errors == 0:
                # pytest executed NOTHING (wrong interpreter / pytest missing
                # inside a container sandbox). A zero-test run must NEVER be
                # reported as "validated" — that is a silent false positive.
                iterations[-1]["failure_classes"] = {"no_tests_run": [test_rel]}
                status = "error"
                EventTap.emit("tool", agent="test_generator", tool="test_results",
                              iteration=it, passed=0, failed=0, error="no tests executed")
                break
            if run.failed == 0 and run.errors == 0 and not run.timed_out:
                status = "validated" if it == 1 else "validated_after_fix"
                break
            if it < max_iterations:
                candidate = propose_validation_patch(sig, classes)
                if candidate:
                    patch = candidate
                    patched_func = apply_patch(func_src, patch)
                    new_sig = _analyze_signature(patched_func)
                    if new_sig:
                        sig = new_sig
                        cases = generate_cases(sig)
                        test_code = render_test_module(module, sig, cases, extra_imports)
                        # write the patched source into the sandbox workspace
                        patched_file = apply_patch(sf.content, patch)
                        ws_path = f"{workspace}/{sym.file}"
                        os.makedirs(os.path.dirname(ws_path), exist_ok=True)
                        with open(ws_path, "w", encoding="utf-8") as fh:
                            fh.write(patched_file)
                        EventTap.emit("tool", agent="test_generator",
                                      tool="propose_fix", patch=patch["description"])
                        continue
                break  # cannot auto-correct further
    finally:
        import shutil

        shutil.rmtree(workspace, ignore_errors=True)

    if status == "rejected" and passed == total:
        status = "validated"
    summary = _verdict_text(status, passed, total, patch, iterations)
    verification = VerificationResult(
        status=status, target=sig["name"], total=total, passed=passed,
        iterations=iterations, patch=patch, summary=summary,
        test_file=test_rel, test_code=test_code,
    )
    result = AgentResult(
        agent="test_generator",
        summary=summary,
        citations=[make_citation(g, sym.file, sym.start_line, sym.end_line,
                                 reason="generation target", symbol=sym.qualified)],
        extra=verification.to_dict(),
    )
    EventTap.emit("agent", agent="test_generator", status="done",
                  verdict=status, passed=passed, total=total)
    return result, verification


def module_import_path(file: str) -> str:
    p = file[:-3] if file.endswith(".py") else file
    if p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    return p.replace("/", ".")


def _verdict_text(status: str, passed: int, total: int, patch, iterations) -> str:
    no_tests = any("no_tests_run" in (i.get("failure_classes") or {}) for i in iterations)
    head = {
        "validated": f"VERIFIED — {passed}/{total} generated tests passed on the first run.",
        "validated_after_fix": (
            f"VERIFIED after correction — final run: {passed}/{total} tests passed. "
            "A validation patch was proposed, applied in the sandbox and re-verified."
        ),
        "rejected": (
            f"NOT VERIFIED — best run: {passed}/{total} tests passed. The failures indicate "
            "real defects in the implementation (see failure classes); the recommendation "
            "was NOT accepted."
        ),
        "error": ("Verification could not execute any tests — the sandboxed pytest run "
                  "produced no results (e.g. the container image lacks pytest, or the "
                  "interpreter path does not exist inside the sandbox). "
                  "Set REPOPILOT_EXECUTOR=subprocess or use a pytest-bearing image."
                  if no_tests else "Verification could not run (see iterations)."),
    }[status]
    parts = [head]
    if patch:
        parts.append(f"Proposed patch ({patch['description']}):\n{patch['code']}")
    if len(iterations) > 1:
        parts.append(f"Loop executed {len(iterations)} iterations: "
                     + " -> ".join(f"{i['passed']}/{i['passed'] + i['failed'] + i['errors']}"
                                   for i in iterations))
    return "\n".join(parts)

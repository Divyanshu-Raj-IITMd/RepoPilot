"""Supervisor: routes each request to the right specialist agent via a
LangGraph StateGraph (with a dependency-free MiniGraph fallback so RepoPilot
runs in CI and offline with zero extras).

    START -> supervisor -> [analyst | search | investigate | review | testgen]
                     ^                          |
                     |                          v
                     +------- verify (testgen only) <----+
                     |
                     +-> compose -> END  (evidence-backed answer)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Callable

from app.agents import code_search, issue_investigator, pr_reviewer, repo_analyst, test_generator
from app.agents.state import AgentState, EventTap

log = logging.getLogger("repopilot.supervisor")

# ------------------------------------------------------------------ routing

_REVIEW_HINTS = re.compile(r"\breview\b|\bpull request\b|\bpr\b|\bdiff\b|\bcode change", re.I)
_TESTGEN_HINTS = re.compile(r"generate (?:unit )?tests?|write tests?|test generation|"
                            r"add tests?|create tests?|tests? for", re.I)
_INVESTIGATE_HINTS = re.compile(r"\bwhy\b|\bfail|failing|error|bug|broken|\b500\b|\b404\b|"
                                r"\bcrash|investigat|debug|root cause|wrong|return http|"
                                r"dangerous|risk|security problem|insecure", re.I)
# architecture questions talk about the WHOLE repository
_ARCH_HINTS = re.compile(
    r"architect|structur|overview|tech stack|organi[sz]|"
    r"what (?:framework|database|language|stack)\b|"
    r"main (?:packages|modules|components|entry)|entry point|"
    r"where are the tests|how many (?:endpoints|files|routes)|"
    r"(?:describe|explain) the (?:repo|project|repository|codebase)|"
    r"what (?:are|is) the (?:main|major) (?:packages|parts|components)|"
    r"what does this (?:repo|project|repository|codebase)",
    re.I)
_SEARCH_HINTS = re.compile(r"\bwhere\b|\bfind\b|\bwhich file\b|\blocate\b|\bshow me\b|"
                           r"how is .* implemented|\bwho (?:calls|uses)\b|\bcallers?\b|"
                           r"\bdepends?\b|\bimports?\b|\binclude\b|\bus(?:es|ed) by\b", re.I)


def classify(question: str, has_diff: bool = False, has_target: bool = False) -> str:
    """Deterministic intent routing.

    Reproducible routing is a feature: the evaluation suite depends on it,
    and an intent classifier does not need an LLM to be reliable.
    """
    q = question or ""
    if has_diff or _REVIEW_HINTS.search(q):
        return "review"
    if _TESTGEN_HINTS.search(q) or (has_target and not q):
        return "testgen"
    if _ARCH_HINTS.search(q):
        return "analyst"
    if _INVESTIGATE_HINTS.search(q):
        return "investigate"
    if _SEARCH_HINTS.search(q):
        return "search"
    return "search"


_TARGET_RE = re.compile(
    r"tests? for (?:the )?(?:function )?`?([\w.]+)`?"
    r"|`([\w.]+)`"
    r"|(?:function|fn|method)\s+([\w.]+)"
    r"|\bfor\s+([\w.]+)\s*(?:function)?$",
)


def extract_target(question: str) -> str:
    m = _TARGET_RE.search(question or "")
    if m:
        return next(g for g in m.groups() if g)
    return ""


AGENT_NAMES = ("analyst", "search", "investigate", "review", "testgen")

# ------------------------------------------------------------------- nodes

_REPO_HOLDER: dict = {}


def _current_repo():
    return _REPO_HOLDER["repo"]


def _get_llm(use_llm: bool = True):
    from app.llm import HeuristicLLM, get_llm
    if not use_llm:
        return HeuristicLLM()  # deterministic mode: agents use template narration
    return get_llm()


def supervisor_node(state: AgentState) -> dict:
    if state.get("final"):
        return {"next": "end"}
    if "route" not in state:
        # first visit: classify the intent and build the plan
        question = state.get("question", "")
        diff = state.get("diff") or ""
        target = state.get("target") or ""
        route = classify(question, has_diff=bool(diff), has_target=bool(target))
        if route == "testgen" and not target:
            target = extract_target(question)
        EventTap.emit("supervisor", action="route", route=route,
                      reason="intent classified from question"
                      + (" + diff" if diff else "") + (" + target" if target else ""))
        updates: dict[str, Any] = {"plan": [], "route": route, "next": route}
        if target:
            updates["target"] = target
        return updates
    plan: list[str] = state.get("plan") or []
    if plan:
        nxt = plan[0]
        return {"plan": plan[1:], "next": nxt}
    return {"next": "end"}


def _agent_node(name: str, run, narrate, use_llm: bool = True) -> Callable:
    def _node(state: AgentState) -> dict:
        repo = _current_repo()
        result = run(repo, state.get("question", ""))
        llm = _get_llm(use_llm)
        if name == "analyst":
            narrative = narrate(repo, result, llm)
        else:
            narrative = narrate(state.get("question", ""), result, llm)
        results = dict(state.get("results") or {})
        results[name] = result.to_dict()
        results[name]["narrative"] = narrative
        return {"results": results, "answer": narrative,
                "citations": results[name]["citations"]}
    return _node


def _make_review_node(use_llm: bool = True) -> Callable:
    def _review_node(state: AgentState) -> dict:
        repo = _current_repo()
        result = pr_reviewer.review(repo, state.get("diff") or "")
        narrative = pr_reviewer.narrate(result, _get_llm(use_llm))
        results = dict(state.get("results") or {})
        results["review"] = result.to_dict()
        results["review"]["narrative"] = narrative
        return {"results": results, "answer": narrative,
                "citations": results["review"]["citations"]}
    return _review_node


def testgen_node(state: AgentState) -> dict:
    repo = _current_repo()
    target = state.get("target") or extract_target(state.get("question", ""))
    result, verification = test_generator.generate_tests(repo, target)
    results = dict(state.get("results") or {})
    results["testgen"] = result.to_dict()
    results["testgen"]["narrative"] = result.summary
    return {"results": results, "answer": result.summary,
            "citations": results["testgen"]["citations"],
            "verification": verification.to_dict()}


def verify_node(state: AgentState) -> dict:
    """Post-verification gate: unverified AI output is never reported as trusted."""
    v = state.get("verification") or {}
    EventTap.emit("verification", status=v.get("status"), passed=v.get("passed"),
                  total=v.get("total"))
    return {}


def compose_answer(state: AgentState) -> dict:
    results = state.get("results") or {}
    parts: list[str] = []
    citations: list[dict] = []
    titles = {"analyst": "Repository analysis", "search": "Code search",
              "investigate": "Investigation", "review": "PR review",
              "testgen": "Test generation & verification"}
    for name in ("analyst", "search", "investigate", "review", "testgen"):
        r = results.get(name)
        if not r:
            continue
        parts.append(f"### {titles[name]}\n\n{r.get('narrative') or r.get('summary', '')}")
        citations.extend(r.get("citations", []))
    answer = "\n\n".join(parts) if parts else "I could not find relevant evidence for that."
    dedup: list[dict] = []
    seen: set[tuple] = set()
    for c in citations:
        key = (c["file"], c["start_line"])
        if key not in seen:
            seen.add(key)
            dedup.append(c)
    return {"answer": answer, "citations": dedup, "final": True}


# ------------------------------------------------------------------- graphs

class MiniGraph:
    """Minimal StateGraph clone: nodes, edges, one conditional edge per node,
    and append-reducer semantics for list state keys."""

    def __init__(self) -> None:
        self.nodes: dict[str, Callable] = {}
        self.edges: dict[str, str] = {}
        self.conditional: dict[str, tuple[Callable, dict]] = {}
        self.entry = None

    def add_node(self, name: str, fn: Callable) -> MiniGraph:
        self.nodes[name] = fn
        return self

    def set_entry_point(self, name: str) -> None:
        self.entry = name

    def add_edge(self, src: str, dst: str) -> None:
        self.edges[src] = dst

    def add_conditional_edges(self, src: str, router: Callable, mapping: dict) -> None:
        self.conditional[src] = (router, mapping)

    def compile(self) -> MiniGraph:
        return self

    def invoke(self, state: dict) -> dict:
        merged: dict = dict(state)
        merged.setdefault("events", [])
        merged.setdefault("results", {})
        cur = self.entry
        guard = 0
        while cur and cur != "__end__" and guard < 40:
            guard += 1
            updates = self.nodes[cur](merged) or {}
            for k, v in updates.items():
                if k in merged and isinstance(merged[k], list) and isinstance(v, list):
                    merged[k] = merged[k] + v
                else:
                    merged[k] = v
            if cur in self.conditional:
                router, mapping = self.conditional[cur]
                cur = mapping.get(router(merged), "__end__")
            else:
                cur = self.edges.get(cur, "__end__")
        return merged


def _route(state: AgentState) -> str:
    return state.get("next", "end")


def build_graph(repo, use_llm: bool = True):
    """Compile the supervisor graph bound to a loaded repo -> (graph, backend)."""
    _REPO_HOLDER["repo"] = repo
    nodes = {
        "analyst": _agent_node("analyst", repo_analyst.analyze, repo_analyst.narrate,
                               use_llm=use_llm),
        "search": _agent_node("search", code_search.search, code_search.narrate,
                              use_llm=use_llm),
        "investigate": _agent_node("investigate", issue_investigator.investigate,
                                   issue_investigator.narrate, use_llm=use_llm),
        "review": _make_review_node(use_llm),
        "testgen": testgen_node,
    }
    mapping = {**{n: n for n in AGENT_NAMES}, "end": "compose"}

    try:
        from langgraph.graph import END, START, StateGraph

        g = StateGraph(AgentState)
        g.add_node("supervisor", supervisor_node)
        for name, fn in nodes.items():
            g.add_node(name, fn)
        g.add_node("verify", verify_node)
        g.add_node("compose", compose_answer)
        g.add_edge(START, "supervisor")
        g.add_conditional_edges("supervisor", _route, mapping)
        for name in ("analyst", "search", "investigate", "review"):
            g.add_edge(name, "supervisor")
        g.add_edge("testgen", "verify")
        g.add_edge("verify", "supervisor")
        g.add_edge("compose", END)
        return g.compile(), "langgraph"
    except ImportError:
        m = MiniGraph()
        m.add_node("supervisor", supervisor_node)
        for name, fn in nodes.items():
            m.add_node(name, fn)
        m.add_node("verify", verify_node)
        m.add_node("compose", compose_answer)
        m.set_entry_point("supervisor")
        m.add_conditional_edges("supervisor", _route, mapping)
        for name in ("analyst", "search", "investigate", "review"):
            m.add_edge(name, "supervisor")
        m.add_edge("testgen", "verify")
        m.add_edge("verify", "supervisor")
        m.add_edge("compose", "__end__")
        return m.compile(), "minigraph"


def run_pipeline(repo, question: str = "", diff: str = "", target: str = "",
                 narrate: bool = True) -> dict:
    """One-shot pipeline run used by the API, CLI and evaluator.

    narrate=False runs the deterministic pipeline (no LLM prose) — used by the
    evaluation suite so metrics are reproducible and provider-independent.
    """
    graph, backend = build_graph(repo, use_llm=narrate)
    state: AgentState = {
        "repo_id": repo.repo_id,
        "question": question,
        "diff": diff,
        "target": target,
        "started_at": time.time(),
        "events": [],
    }
    try:
        final = graph.invoke(state)
    except Exception as exc:  # noqa: BLE001
        log.exception("pipeline failed")
        final = {**state, "answer": f"Pipeline error: {exc}", "error": str(exc)}
    final["duration_ms"] = round((time.time() - state["started_at"]) * 1000, 1)
    final["graph_backend"] = backend
    final.setdefault("citations", [])
    final.setdefault("verification", None)
    return final

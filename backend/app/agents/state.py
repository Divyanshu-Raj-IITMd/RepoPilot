"""Shared agent state (LangGraph-compatible TypedDict) + the event tap for tracing."""

from __future__ import annotations

import operator
import threading
import time
from typing import Annotated, Any

from typing_extensions import TypedDict


def _merge_list(left: list, right: list) -> list:
    return left + right


class AgentState(TypedDict, total=False):
    """State flowing through the supervisor graph.

    `events` uses an append reducer so every node's trace entries accumulate.
    """

    repo_id: str
    question: str
    diff: str                       # unified diff for PR review tasks
    target: str                     # symbol target for test generation

    route: str                      # analyst | search | investigate | review | testgen
    next: str                       # next node chosen by the supervisor
    final: bool                     # set once the answer is composed
    plan: list[str]                 # remaining agent steps
    results: dict[str, dict]        # agent name -> AgentResult.to_dict()
    answer: str
    citations: list[dict]
    verification: dict
    events: Annotated[list[dict], operator.add]
    error: str | None
    started_at: float
    duration_ms: float


class EventTap:
    """Thread-local tap agents push trace events into (streamed over SSE)."""

    _local = threading.local()

    @classmethod
    def bind(cls) -> None:
        cls._local.queue = None

    @classmethod
    def attach(cls, queue) -> None:
        cls._local.queue = queue

    @classmethod
    def detach(cls) -> None:
        cls._local.queue = None

    @classmethod
    def emit(cls, step: str, **detail: Any) -> dict:
        event = {"step": step, "ts": round(time.time(), 3), **detail}
        q = getattr(cls._local, "queue", None)
        if q is not None:
            q.put(event)
        return event

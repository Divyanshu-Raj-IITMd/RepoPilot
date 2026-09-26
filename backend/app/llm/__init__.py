"""LLM providers — all free.

Priority (configurable via REPOPILOT_LLM_PROVIDER):
  groq > gemini > openrouter > ollama > heuristic

  * groq       — free tier, OpenAI-compatible REST (llama-3.3-70b-versatile)
  * gemini     — Google AI Studio free tier (gemini-2.0-flash)
  * openrouter — free community models
  * ollama     — 100% local, no API key, no data leaves the machine
  * heuristic  — no LLM at all: deterministic templates over the evidence pack.
                 RepoPilot stays fully functional offline (agents' structured
                 findings never depend on an LLM).

Every provider implements complete(system, user, json_mode=False) and reports
availability. All HTTP calls go through httpx with timeouts; content passed to
any remote provider is first passed through app.sandbox.secret_scanner.redact.
"""

from __future__ import annotations

import logging
import os

import httpx

from app.config import Settings, get_settings
from app.sandbox.secret_scanner import redact

log = logging.getLogger("repopilot.llm")


class LLMUnavailable(Exception):
    pass


class BaseLLM:
    name = "base"
    available = False
    remote = False

    def complete(self, system: str, user: str, json_mode: bool = False,
                 max_tokens: int = 1500) -> str:
        raise LLMUnavailable(f"{self.name} is not available")

    def describe(self) -> dict:
        return {"provider": self.name, "available": self.available,
                "remote": self.remote, "model": getattr(self, "model", None)}


class HeuristicLLM(BaseLLM):
    """Offline provider: no completion. Agents fall back to template narration."""

    name = "heuristic"
    available = False
    remote = False


class OpenAICompatLLM(BaseLLM):
    """OpenAI-compatible chat completions (Groq, OpenRouter, LM Studio, ...)."""

    available = True
    remote = True

    def __init__(self, base_url: str, api_key: str, model: str, name: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.name = name

    def complete(self, system: str, user: str, json_mode: bool = False,
                 max_tokens: int = 1500) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": redact(user)},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


class OllamaLLM(BaseLLM):
    """Local models via Ollama's native /api/chat. Free and private."""

    name = "ollama"
    remote = False

    def __init__(self, base_url: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.available = self._probe()

    def _probe(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/api/tags", timeout=3)
            if r.status_code != 200:
                return False
            models = [m.get("name", "") for m in r.json().get("models", [])]
            if models and self.model not in models:
                # fall back to the first installed model rather than failing
                self.model = models[0]
            return True
        except Exception:
            return False

    def complete(self, system: str, user: str, json_mode: bool = False,
                 max_tokens: int = 1500) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json" if json_mode else "",
            "options": {"temperature": 0.1, "num_predict": max_tokens},
        }
        resp = httpx.post(f"{self.base_url}/api/chat", json=payload, timeout=180)
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class GeminiLLM(BaseLLM):
    """Google AI Studio (Gemini) free tier via the REST API."""

    name = "gemini"
    remote = True
    available = True

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def complete(self, system: str, user: str, json_mode: bool = False,
                 max_tokens: int = 1500) -> str:
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": redact(user)}]}],
            "generationConfig": {
                "temperature": 0.1, "maxOutputTokens": max_tokens,
                "responseMimeType": "application/json" if json_mode else "text/plain",
            },
        }
        resp = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}",
            json=body, timeout=90,
        )
        resp.raise_for_status()
        parts = resp.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in parts)


_CACHED: BaseLLM | None = None


def get_llm(settings: Settings | None = None, refresh: bool = False) -> BaseLLM:
    """Select the best available free provider. Cached per process."""
    global _CACHED
    if _CACHED is not None and not refresh:
        return _CACHED
    s = settings or get_settings()
    env = os.environ
    order = {
        "groq": lambda: OpenAICompatLLM("https://api.groq.com/openai/v1", env["GROQ_API_KEY"],
                                        s.groq_model, "groq"),
        "gemini": lambda: GeminiLLM(env["GEMINI_API_KEY"] or env["GOOGLE_API_KEY"], s.gemini_model),
        "openrouter": lambda: OpenAICompatLLM("https://openrouter.ai/api/v1",
                                              env["OPENROUTER_API_KEY"],
                                              s.openrouter_model, "openrouter"),
        "ollama": lambda: OllamaLLM(s.ollama_url, s.ollama_model),
        "heuristic": lambda: HeuristicLLM(),
    }
    choice = s.llm_provider.lower()
    if choice in ("", "auto"):
        for name in ("groq", "gemini", "openrouter", "ollama"):
            key = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY or GOOGLE_API_KEY",
                   "openrouter": "OPENROUTER_API_KEY", "ollama": None}[name]
            if name == "ollama":
                cand = order["ollama"]()
                if cand.available:
                    _CACHED = cand
                    return _CACHED
                continue
            if env.get(key.split(" or ")[0]) or (key.endswith("GOOGLE_API_KEY") and env.get("GOOGLE_API_KEY")):
                _CACHED = order[name]()
                return _CACHED
        _CACHED = HeuristicLLM()
        return _CACHED
    if choice == "gemini" and not (env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY")):
        _CACHED = HeuristicLLM()
        return _CACHED
    if choice in ("groq", "openrouter") and not env.get(f"{choice.upper()}_API_KEY"):
        _CACHED = HeuristicLLM()
        return _CACHED
    _CACHED = order.get(choice, order["heuristic"])()
    return _CACHED


def narrate_or_none(llm: BaseLLM, system: str, user: str, max_tokens: int = 1200) -> str | None:
    """Try an LLM narration; return None if unavailable so callers use templates."""
    if not llm.available:
        return None
    try:
        out = llm.complete(system, user, max_tokens=max_tokens)
        return out if out and out.strip() else None
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM narration failed (%s): %s", llm.name, exc)
        return None

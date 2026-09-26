"""Configuration via environment variables with sane defaults (local-first, free)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    """Runtime settings. Everything has a working free default."""

    data_dir: str = field(default_factory=lambda: os.environ.get(
        "REPOPILOT_DATA_DIR",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".repopilot"),
    ))

    # --- LLM provider: auto | ollama | groq | gemini | openrouter | heuristic
    llm_provider: str = field(default_factory=lambda: os.environ.get("REPOPILOT_LLM_PROVIDER", "auto"))
    ollama_url: str = field(default_factory=lambda: os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
    ollama_model: str = field(default_factory=lambda: os.environ.get("REPOPILOT_OLLAMA_MODEL", "qwen2.5-coder:7b"))
    groq_model: str = field(default_factory=lambda: os.environ.get("REPOPILOT_GROQ_MODEL", "llama-3.3-70b-versatile"))
    gemini_model: str = field(default_factory=lambda: os.environ.get("REPOPILOT_GEMINI_MODEL", "gemini-2.0-flash"))
    openrouter_model: str = field(default_factory=lambda: os.environ.get(
        "REPOPILOT_OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"))

    # --- Embeddings: auto | hash | sbert
    embedder: str = field(default_factory=lambda: os.environ.get("REPOPILOT_EMBEDDER", "auto"))
    sbert_model: str = field(default_factory=lambda: os.environ.get(
        "REPOPILOT_SBERT_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))

    # --- Execution sandbox: auto | docker | subprocess
    executor: str = field(default_factory=lambda: os.environ.get("REPOPILOT_EXECUTOR", "auto"))

    # --- Retrieval
    retrieval_top_k: int = field(default_factory=lambda: int(os.environ.get("REPOPILOT_TOP_K", "10")))

    # --- Verification loop
    verify_max_iterations: int = field(default_factory=lambda: int(os.environ.get("REPOPILOT_VERIFY_ITERS", "2")))
    test_timeout: int = field(default_factory=lambda: int(os.environ.get("REPOPILOT_TEST_TIMEOUT", "120")))

    # --- API
    cors_origins: str = field(default_factory=lambda: os.environ.get("REPOPILOT_CORS", "*"))
    demo_repo_path: str = field(default_factory=lambda: os.environ.get(
        "REPOPILOT_DEMO_REPO",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "demo-repos", "ecommerce-api"),
    ))

    @property
    def clones_dir(self) -> str:
        return os.path.join(self.data_dir, "clones")

    @property
    def index_dir(self) -> str:
        return os.path.join(self.data_dir, "indexes")

    @property
    def registry_path(self) -> str:
        return os.path.join(self.data_dir, "repos.json")

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.clones_dir, self.index_dir):
            os.makedirs(d, exist_ok=True)


def get_settings() -> Settings:
    return Settings()

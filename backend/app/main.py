"""FastAPI application entrypoint.

Run:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.llm import get_llm
from app.repo_manager import RepoManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

settings = get_settings()
settings.ensure_dirs()

app = FastAPI(title="RepoPilot", version=__version__,
              description="Agentic AI software engineering assistant")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(router)


class _State:
    manager = RepoManager(settings)


router.state = _State()  # type: ignore[attr-defined]


@app.on_event("startup")
def _startup() -> None:
    llm = get_llm()
    logging.getLogger("repopilot").info(
        "RepoPilot %s ready — LLM provider: %s (available=%s)",
        __version__, llm.name, llm.available,
    )

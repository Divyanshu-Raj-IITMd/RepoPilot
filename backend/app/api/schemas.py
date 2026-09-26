"""Pydantic schemas for the REST API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepoIn(BaseModel):
    source: str = Field(..., description="git URL or local path")
    name: str | None = None
    repo_id: str | None = None


class ChatIn(BaseModel):
    repo_id: str
    message: str
    target: str | None = None  # explicit symbol for test generation


class ReviewIn(BaseModel):
    repo_id: str
    diff: str


class TestGenIn(BaseModel):
    repo_id: str
    target: str  # function/class name


class EvalIn(BaseModel):
    repo_id: str | None = None
    categories: list[str] | None = None
    limit: int | None = None

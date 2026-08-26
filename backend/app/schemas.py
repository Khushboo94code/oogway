"""Request/response contracts (validation + clear API shapes)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---- sessions --------------------------------------------------------------
class SessionCreate(BaseModel):
    title: str = Field(default="New chat", max_length=200)
    user_metadata: dict[str, Any] = Field(default_factory=dict)


class SessionOut(BaseModel):
    id: UUID
    title: str
    user_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ---- messages / citations / artifacts -------------------------------------
class Citation(BaseModel):
    episode_title: str
    guest: str | None = None
    source_url: str | None = None
    publish_date: date | None = None
    chunk_id: UUID | None = None
    score: float | None = None


class Artifact(BaseModel):
    type: Literal["markdown", "html"]
    title: str = "Artifact"
    content: str


class MessageOut(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    provider: str | None = None
    model: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    artifact: Artifact | None = None
    created_at: datetime


# ---- chat ------------------------------------------------------------------
class ChatRequest(BaseModel):
    session_id: UUID
    message: str = Field(min_length=1, max_length=8000)


# ---- health ----------------------------------------------------------------
class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    provider: str
    model: str
    agent_backend: str
    checks: dict[str, Any]

"""Session + message endpoints. Each session keeps independent context."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from .. import repository as repo
from ..schemas import MessageOut, SessionCreate, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=201)
async def create_session(body: SessionCreate) -> SessionOut:
    row = await repo.create_session(body.title, body.user_metadata)
    return SessionOut(**row)


@router.get("", response_model=list[SessionOut])
async def list_sessions() -> list[SessionOut]:
    rows = await repo.list_sessions()
    return [SessionOut(**r) for r in rows]


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: UUID) -> SessionOut:
    row = await repo.get_session(session_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionOut(**row)


@router.get("/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(session_id: UUID) -> list[MessageOut]:
    if await repo.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    rows = await repo.list_messages(session_id)
    return [MessageOut(**r) for r in rows]

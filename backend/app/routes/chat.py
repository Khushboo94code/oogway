"""Chat endpoint: streams a grounded answer as Server-Sent Events."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from .. import repository as repo
from ..agent.orchestrator import sse_stream
from ..schemas import ChatRequest

router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(body: ChatRequest) -> StreamingResponse:
    if await repo.get_session(body.session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return StreamingResponse(
        sse_stream(body.session_id, body.message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable proxy buffering for token streaming
        },
    )

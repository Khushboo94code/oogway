"""Artifact endpoints: expose the render policy and a server-side sanitize pass
(defense in depth; the enforced boundary is the sandboxed iframe + CSP)."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..security.sanitize import POLICY, sanitize_html

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


class SanitizeRequest(BaseModel):
    content: str


@router.get("/policy")
async def policy() -> dict:
    return {"policy": POLICY}


@router.post("/sanitize")
async def sanitize(body: SanitizeRequest) -> dict:
    clean, report = sanitize_html(body.content)
    return {"content": clean, "report": report}

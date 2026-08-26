"""Chat orchestration: persist → route intent → retrieve grounded context →
produce a grounded answer / essay / artifact → persist with citations. Emits SSE.

Generation backend is selected by AGENT_BACKEND:
  - `litellm`   : direct provider-agnostic path (implemented here; reliable demo path)
  - `agent_sdk` : Claude Agent SDK via the LiteLLM proxy (added in the agent-SDK backend,
                  which falls back to this path on failure)."""
from __future__ import annotations

import json
import logging
from typing import AsyncIterator
from uuid import UUID

from .. import repository as repo
from ..config import get_settings
from ..llm import gateway
from ..llm.gateway import LLMError
from ..rag.retrieve import retrieve_context
from ..security.sanitize import sanitize_html
from .backends import claude_sdk
from .prompts import build_messages
from .router import route
from .skills import build_artifact_messages, build_essay_messages, finalize_artifact, wants_html

log = logging.getLogger(__name__)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _title_from(message: str) -> str:
    t = " ".join(message.strip().split())
    return (t[:48] + "…") if len(t) > 49 else t


async def sse_stream(session_id: UUID, user_message: str) -> AsyncIterator[str]:
    provider, model_label = gateway.active_labels()
    intent = route(user_message)

    await repo.add_message(session_id, "user", user_message)
    sess = await repo.get_session(session_id)
    new_title = _title_from(user_message) if sess and sess.get("title") == "New chat" else None
    await repo.touch_session(session_id, title=new_title)

    yield _sse("start", {"intent": intent, "provider": provider, "model": model_label})

    retrieval = await retrieve_context(user_message)
    history = await repo.get_history(session_id)
    if history and history[-1]["role"] == "user" and history[-1]["content"] == user_message:
        history = history[:-1]

    citations = retrieval["citations"] if retrieval["grounded"] else []
    ctx = {
        "session_id": session_id,
        "history": history,
        "retrieval": retrieval,
        "citations": citations,
        "question": user_message,
        "provider": provider,
        "model_label": model_label,
        "intent": intent,
    }

    if intent == "essay":
        gen = _handle_essay(ctx)
    elif intent == "artifact":
        gen = _handle_artifact(ctx)
    else:
        gen = _handle_chat(ctx)
    async for event in gen:
        yield event


def _meta(ctx: dict, artifact: dict | None = None, security_report: dict | None = None) -> str:
    return _sse("meta", {
        "citations": ctx["citations"],
        "artifact": artifact,
        "security_report": security_report,
        "provider": ctx["provider"],
        "model": ctx["model_label"],
        "grounded": ctx["retrieval"]["grounded"],
        "intent": ctx["intent"],
        "top_score": round(ctx["retrieval"]["top_score"], 4),
    })


async def _persist_error(ctx: dict, exc: Exception) -> str:
    note = f"The model call failed ({ctx['provider']}). Details: {exc}"
    await repo.add_message(ctx["session_id"], "assistant", note,
                           provider=ctx["provider"], model=ctx["model_label"])
    return _sse("error", {"type": "llm_error", "message": str(exc)})


async def _handle_chat(ctx: dict) -> AsyncIterator[str]:
    settings = get_settings()
    parts: list[str] = []
    used_sdk = False

    # Faithful path: Claude Agent SDK via the LiteLLM proxy. Falls back to the
    # direct path if the SDK is unavailable, or errors *before* emitting tokens.
    if settings.agent_backend == "agent_sdk" and claude_sdk.available():
        sdk_citations: list = []
        try:
            async for delta in claude_sdk.stream_answer(ctx["history"], ctx["question"], sdk_citations):
                parts.append(delta)
                yield _sse("token", {"text": delta})
            used_sdk = True
            if sdk_citations:
                ctx["citations"] = sdk_citations
        except Exception as exc:  # noqa: BLE001
            log.warning("Agent SDK path failed (%s).", exc)
            if parts:
                # Already streamed partial output — don't restart; finish gracefully.
                used_sdk = True
            else:
                log.info("Falling back to direct LiteLLM path.")

    if not used_sdk:
        messages = build_messages(ctx["history"], ctx["retrieval"]["context_text"], ctx["question"])
        try:
            async for delta in gateway.stream_chat(messages, max_tokens=1200):
                parts.append(delta)
                yield _sse("token", {"text": delta})
        except LLMError as exc:
            yield await _persist_error(ctx, exc)
            yield _sse("done", {})
            return

    answer = "".join(parts).strip() or "(no output was produced)"
    await repo.add_message(ctx["session_id"], "assistant", answer,
                           provider=ctx["provider"], model=ctx["model_label"],
                           citations=ctx["citations"])
    yield _meta(ctx)
    yield _sse("done", {})


async def _handle_essay(ctx: dict) -> AsyncIterator[str]:
    messages = build_essay_messages(ctx["history"], ctx["retrieval"]["context_text"], ctx["question"])
    parts: list[str] = []
    try:
        async for delta in gateway.stream_chat(messages, max_tokens=3200, temperature=0.6):
            parts.append(delta)
            yield _sse("token", {"text": delta})
    except LLMError as exc:
        yield await _persist_error(ctx, exc)
        yield _sse("done", {})
        return

    essay = "".join(parts).strip() or "(no output was produced)"
    artifact = {"type": "markdown", "title": f"Essay: {ctx['question'][:48]}", "content": essay}
    await repo.add_message(ctx["session_id"], "assistant", essay,
                           provider=ctx["provider"], model=ctx["model_label"],
                           citations=ctx["citations"], artifact=artifact)
    yield _meta(ctx, artifact=artifact)
    yield _sse("done", {})


async def _handle_artifact(ctx: dict) -> AsyncIterator[str]:
    prefer_html = wants_html(ctx["question"])
    messages = build_artifact_messages(
        ctx["history"], ctx["retrieval"]["context_text"], ctx["question"], prefer_html
    )
    try:
        raw = await gateway.complete_chat(messages, max_tokens=3500, temperature=0.4)
    except LLMError as exc:
        yield await _persist_error(ctx, exc)
        yield _sse("done", {})
        return

    artifact = finalize_artifact(raw, ctx["question"], prefer_html)
    security_report = None
    if artifact["type"] == "html":
        clean, security_report = sanitize_html(artifact["content"])
        artifact["content"] = clean

    note = f'Generated a {artifact["type"]} artifact: "{artifact["title"]}". See the artifact panel →'
    await repo.add_message(ctx["session_id"], "assistant", note,
                           provider=ctx["provider"], model=ctx["model_label"],
                           citations=ctx["citations"], artifact=artifact)
    yield _sse("token", {"text": note})
    yield _meta(ctx, artifact=artifact, security_report=security_report)
    yield _sse("done", {})

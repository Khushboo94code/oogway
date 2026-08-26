"""Claude Agent SDK backend (the faithful, mandated path).

The Agent SDK drives the Claude Code CLI, which speaks the Anthropic Messages API.
Since we have no Anthropic key, we point it at the LiteLLM proxy (Anthropic
`/v1/messages` passthrough) via ANTHROPIC_BASE_URL, so it runs on OpenAI (cloud)
or Ollama (local) — a documented pattern. The agent does real agentic retrieval
through an in-process MCP tool.

This path is best-effort: the orchestrator falls back to the direct LiteLLM path
if the SDK is unavailable or errors, so the demo never breaks."""
from __future__ import annotations

import logging
from typing import AsyncIterator

from ..prompts import GROUNDED_SYSTEM
from ... import runtime
from ...config import get_settings
from ...rag.retrieve import retrieve_context

log = logging.getLogger(__name__)

try:
    from claude_agent_sdk import (
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        TextBlock,
        create_sdk_mcp_server,
        tool,
    )

    _SDK_OK = True
    _IMPORT_ERR: Exception | None = None
except Exception as exc:  # noqa: BLE001 — SDK optional at import time
    _SDK_OK = False
    _IMPORT_ERR = exc


SDK_SYSTEM = (
    GROUNDED_SYSTEM
    + "\n\nAlways call the `retrieve_transcripts` tool FIRST to fetch relevant excerpts, "
    "then answer using only those excerpts and cite them as [1], [2], ..."
)


def available() -> bool:
    return _SDK_OK


def _prompt_with_history(history: list[dict], question: str) -> str:
    if not history:
        return question
    convo = "\n".join(f"{h['role'].upper()}: {h['content']}" for h in history[-6:])
    return f"Earlier conversation:\n{convo}\n\nCurrent question: {question}"


def _build_server(citations_out: list):
    @tool(
        "retrieve_transcripts",
        "Search Lenny's Podcast transcripts for excerpts relevant to a query. "
        "Returns numbered excerpts to ground the answer.",
        {"query": str},
    )
    async def retrieve_transcripts(args):
        res = await retrieve_context(args["query"])
        citations_out.clear()
        if res["grounded"]:
            citations_out.extend(res["citations"])
        text = res["context_text"] or "(no relevant excerpts found)"
        return {"content": [{"type": "text", "text": text}]}

    return create_sdk_mcp_server(name="lenny", version="1.0.0", tools=[retrieve_transcripts])


async def stream_answer(
    history: list[dict], question: str, citations_out: list
) -> AsyncIterator[str]:
    """Stream the agent's answer text. Fills `citations_out` via the retrieval tool.
    Raises on any SDK failure so the caller can fall back."""
    if not _SDK_OK:
        raise RuntimeError(f"claude-agent-sdk unavailable: {_IMPORT_ERR}")

    s = get_settings()
    server = _build_server(citations_out)
    options = ClaudeAgentOptions(
        system_prompt=SDK_SYSTEM,
        model=runtime.proxy_model_name(),
        mcp_servers={"lenny": server},
        allowed_tools=["mcp__lenny__retrieve_transcripts"],
        max_turns=4,
        env={
            "ANTHROPIC_BASE_URL": s.litellm_proxy_url,
            "ANTHROPIC_AUTH_TOKEN": s.litellm_master_key,
            "ANTHROPIC_MODEL": runtime.proxy_model_name(),
        },
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(_prompt_with_history(history, question))
        async for message in client.receive_response():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock) and block.text:
                        yield block.text

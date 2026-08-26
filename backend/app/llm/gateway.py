"""Provider-agnostic LLM gateway (direct path). One function shape for both
providers; `LLM_PROVIDER` picks OpenAI vs Ollama. Includes a graceful fallback:
if cloud is selected but no OpenAI key is present, we drop to local Ollama."""
from __future__ import annotations

import logging
from typing import AsyncIterator

import litellm

from .. import runtime
from ..config import get_settings

log = logging.getLogger(__name__)

# Silently drop provider-specific params a target model doesn't support.
litellm.drop_params = True


class LLMError(Exception):
    """Raised for any model-call failure (surfaced to the client as a typed error)."""


def _resolve() -> tuple[dict, str, str]:
    """Return (litellm_params, provider_label, model_label) from the live runtime
    selection, honoring the cloud→local fallback when no OpenAI key is present."""
    s = get_settings()
    if runtime.is_cloud() and s.openai_api_key:
        m = runtime.openai_model()
        return ({"model": f"openai/{m}", "api_key": s.openai_api_key}, "cloud", f"OpenAI · {m}")
    if runtime.is_cloud() and not s.openai_api_key:
        log.warning("Cloud selected but OPENAI_API_KEY missing → falling back to local Ollama")
    m = runtime.ollama_model()
    return ({"model": f"ollama_chat/{m}", "api_base": s.ollama_url}, "local", f"Ollama · {m}")


def active_labels() -> tuple[str, str]:
    _, provider, model = _resolve()
    return provider, model


async def stream_chat(messages: list[dict], max_tokens: int = 1200,
                      temperature: float = 0.3) -> AsyncIterator[str]:
    params, _, _ = _resolve()
    try:
        resp = await litellm.acompletion(
            messages=messages, stream=True, max_tokens=max_tokens,
            temperature=temperature, timeout=600, **params,
        )
        async for chunk in resp:
            try:
                delta = chunk.choices[0].delta.content
            except (AttributeError, IndexError):
                delta = None
            if delta:
                yield delta
    except Exception as exc:  # noqa: BLE001
        raise LLMError(str(exc)) from exc


async def complete_chat(messages: list[dict], max_tokens: int = 2048,
                        temperature: float = 0.3) -> str:
    params, _, _ = _resolve()
    try:
        resp = await litellm.acompletion(
            messages=messages, stream=False, max_tokens=max_tokens,
            temperature=temperature, timeout=600, **params,
        )
    except Exception as exc:  # noqa: BLE001
        raise LLMError(str(exc)) from exc
    return resp.choices[0].message.content or ""

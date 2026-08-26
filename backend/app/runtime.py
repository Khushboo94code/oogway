"""Runtime-mutable model selection, so the UI can switch provider/model live without
a restart. Initialized from env (LLM_PROVIDER / OPENAI_MODEL / OLLAMA_MODEL) on first
use; overridable in-memory via set_selection(). Single-process (one uvicorn worker)."""
from __future__ import annotations

import logging

import httpx

from .config import get_settings

log = logging.getLogger(__name__)

_provider: str | None = None  # "cloud" | "local"
_openai_model: str | None = None
_ollama_model: str | None = None


def _ensure() -> None:
    global _provider, _openai_model, _ollama_model
    if _provider is None:
        s = get_settings()
        _provider = s.llm_provider
        _openai_model = s.openai_model
        _ollama_model = s.ollama_model


def get_provider() -> str:
    _ensure()
    return _provider  # type: ignore[return-value]


def is_cloud() -> bool:
    return get_provider() == "cloud"


def openai_model() -> str:
    _ensure()
    return _openai_model  # type: ignore[return-value]


def ollama_model() -> str:
    _ensure()
    return _ollama_model  # type: ignore[return-value]


def current_model() -> str:
    return openai_model() if is_cloud() else ollama_model()


def active_model_label() -> str:
    return f"OpenAI · {openai_model()}" if is_cloud() else f"Ollama · {ollama_model()}"


def proxy_model_name() -> str:
    """Model name the LiteLLM proxy routes on (Agent SDK path)."""
    return "lenny-cloud" if is_cloud() else "lenny-local"


def current_selection_id() -> str:
    return f"{get_provider()}:{current_model()}"


def set_selection(provider: str, model: str | None) -> None:
    global _provider, _openai_model, _ollama_model
    _ensure()
    if provider not in ("cloud", "local"):
        raise ValueError("provider must be 'cloud' or 'local'")
    _provider = provider
    if model:
        if provider == "cloud":
            _openai_model = model
        else:
            _ollama_model = model
    log.info("Model selection changed → provider=%s model=%s", _provider, current_model())


async def _ollama_models() -> list[str]:
    s = get_settings()
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            r = await client.get(f"{s.ollama_url}/api/tags")
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
        # exclude the embedding model; keep chat models
        return [n for n in names if n and s.embed_model not in n]
    except Exception:  # noqa: BLE001 — Ollama may be down; fall back to configured model
        return []


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for i in items:
        if i and i not in seen:
            seen.add(i)
            out.append(i)
    return out


async def available_options() -> list[dict]:
    """Dropdown options: cloud (OpenAI) + local (Ollama, discovered live)."""
    s = get_settings()
    has_key = bool(s.openai_api_key)
    opts: list[dict] = []
    for m in _unique(["gpt-4o-mini", "gpt-4.1", s.openai_model]):
        opts.append({"id": f"cloud:{m}", "provider": "cloud", "model": m,
                     "label": f"OpenAI · {m}", "available": has_key})
    local = await _ollama_models() or [s.ollama_model]
    for m in _unique(local):
        opts.append({"id": f"local:{m}", "provider": "local", "model": m,
                     "label": f"Ollama · {m}", "available": True})
    return opts

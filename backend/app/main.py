"""FastAPI application entrypoint: logging, request-id correlation, structured
error envelopes, dependency-aware startup, and route mounting."""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import runtime
from .config import get_settings
from .db import close_pool, init_db
from .logging_config import configure_logging, request_id_var
from .routes import artifacts, chat, config, health, sessions

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    configure_logging(s.log_level)
    log.info("Starting Lenny Growth Assistant (provider=%s, agent=%s)", s.llm_provider, s.agent_backend)
    try:
        await init_db()
    except Exception:  # noqa: BLE001 — stay up so /health can report the failure
        log.exception("init_db failed at startup; /health will show db degraded")
    yield
    await close_pool()


app = FastAPI(title="The Lenny Growth Assistant", version="0.1.0", lifespan=lifespan)

_settings = get_settings()
_cors_kwargs: dict = dict(
    allow_origins=_settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# In local dev, Vite may pick any free port (5173, 5174, …) — allow any localhost origin
# so the SPA works regardless of which port it landed on.
if _settings.app_env == "local":
    _cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
app.add_middleware(CORSMiddleware, **_cors_kwargs)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
    finally:
        request_id_var.reset(token)
    response.headers["x-request-id"] = rid
    return response


def _envelope(status_code: int, err_type: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"type": err_type, "message": message, "request_id": request_id_var.get()}},
    )


@app.exception_handler(RequestValidationError)
async def _validation_handler(request: Request, exc: RequestValidationError):
    return _envelope(422, "validation_error", str(exc.errors()))


@app.exception_handler(StarletteHTTPException)
async def _http_handler(request: Request, exc: StarletteHTTPException):
    return _envelope(exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(Exception)
async def _generic_handler(request: Request, exc: Exception):
    log.exception("Unhandled error")
    return _envelope(500, "internal_error", str(exc))


app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(chat.router)
app.include_router(artifacts.router)
app.include_router(config.router)


@app.get("/", tags=["meta"])
async def root() -> dict:
    return {
        "name": "The Lenny Growth Assistant",
        "provider": runtime.get_provider(),
        "model": runtime.active_model_label(),
        "docs": "/docs",
        "health": "/health",
    }

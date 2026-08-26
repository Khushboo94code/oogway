FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Node is required by the Claude Agent SDK (it drives the bundled Claude Code CLI).
# git/curl are used by the transcript ingestion step.
RUN apt-get update && apt-get install -y --no-install-recommends \
        nodejs npm git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# Install dependencies first (better layer caching), then the app.
COPY pyproject.toml ./
COPY app ./app
# Agent Skills are discovered from .claude/skills by the Claude Agent SDK.
COPY .claude ./.claude
COPY tests ./tests
RUN uv pip install --system --no-cache ".[dev]"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

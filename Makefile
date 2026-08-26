.PHONY: up down logs ingest test dev-api dev-web

## Docker (primary path)
up:            ## build + start the full stack
	docker compose up --build -d

down:          ## stop the stack
	docker compose down

logs:          ## tail all logs
	docker compose logs -f

ingest:        ## load Lenny transcripts into the knowledge base (run once)
	docker compose run --rm api python -m app.rag.ingest

test:          ## run backend tests inside the api image
	docker compose run --rm api pytest -q

## Native dev (no Docker; needs local Postgres+pgvector and Ollama)
dev-api:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-web:
	cd frontend && npm install && npm run dev

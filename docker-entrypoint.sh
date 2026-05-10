#!/bin/bash
set -e

echo "[EROCK] Running database migrations..."
alembic upgrade head

echo "[EROCK] Starting Elephant Rock backend..."
exec uvicorn backend.api.app:app --host 0.0.0.0 --port 8000 ${EROCK_UVICORN_ARGS:-}

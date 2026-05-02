# ── Stage 1: Build ───────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
COPY pyproject.toml ./
RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: Runtime ────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY backend/ backend/
COPY alembic/ alembic/
COPY alembic.ini alembic.ini

# Create data directory for SQLite default (HB-01)
RUN mkdir -p /app/data

# Non-root user for security
RUN groupadd -r erock && useradd -r -g erock -d /app erock
RUN chown -R erock:erock /app /app/data
USER erock

EXPOSE 8000

# Default environment — can be overridden by docker-compose / env file
ENV EROCK_DATABASE_URL=postgresql+psycopg2://erock:erock@postgres:5432/elephant_rock

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

CMD ["uvicorn", "backend.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

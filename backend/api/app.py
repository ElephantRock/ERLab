"""Elephant Rock Research API — FastAPI application."""

from fastapi import FastAPI

from backend.api.routes import gaps, ideas, knowledge, memory, pipeline, status

app = FastAPI(
    title="Elephant Rock Research API",
    version="0.1.0",
    description="AI/NLP Research Idea Generation Platform",
)

app.include_router(pipeline.router, prefix="/api/v1/pipeline", tags=["pipeline"])
app.include_router(ideas.router, prefix="/api/v1/ideas", tags=["ideas"])
app.include_router(gaps.router, prefix="/api/v1/gaps", tags=["gaps"])
app.include_router(knowledge.router, prefix="/api/v1/knowledge", tags=["knowledge"])
app.include_router(status.router, prefix="/api/v1/status", tags=["status"])
app.include_router(memory.router, prefix="/api/v1/memory", tags=["memory"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}

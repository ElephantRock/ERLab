"""BATCH-45: Gap-to-Paper Navigation & Related Gaps tests."""
from unittest.mock import MagicMock

from fastapi import FastAPI

from backend.api.routes.gaps import router

app = FastAPI()
app.include_router(router, prefix="/gaps")


def _mock_gap():
    g = MagicMock()
    g.id = 1
    g.title = "Test Gap"
    g.pipeline_run_id = 1
    g.related_clusters = "[1, 3]"
    return g


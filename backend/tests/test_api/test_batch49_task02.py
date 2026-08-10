"""BATCH-49 TASK-02: Sandboxed Experiment Execution tests."""
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from backend.api.errors import APIError
from backend.api.routes.experiments import router

app = FastAPI()


@app.exception_handler(APIError)
async def api_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


app.include_router(router, prefix="/experiments")


def test_49_02_01_security_validator_blocks_dangerous_imports():
    """Security validator blocks dangerous imports."""
    from backend.pipeline.experiment.validator import SecurityValidator

    validator = SecurityValidator()
    violations = validator.validate("import os\nprint('hello')")
    assert len(violations) > 0
    assert any("os" in v for v in violations)

    violations = validator.validate("import subprocess\nsubprocess.run(['ls'])")
    assert len(violations) > 0
    assert any("subprocess" in v for v in violations)

    violations = validator.validate("eval('1+1')")
    assert len(violations) > 0
    assert any("eval" in v for v in violations)


def test_49_02_02_security_validator_allows_safe_code():
    """Security validator allows safe code."""
    from backend.pipeline.experiment.validator import SecurityValidator

    validator = SecurityValidator()
    violations = validator.validate("x = 1 + 2\nprint(x)")
    assert len(violations) == 0

    violations = validator.validate("def hello():\n    return 'world'")
    assert len(violations) == 0


def test_49_02_03_returns_403_when_disabled():
    """Returns 403 when experiment_enabled=False."""
    mock_settings = MagicMock()
    mock_settings.experiment_enabled = False
    with patch("backend.api.routes.experiments.get_settings", return_value=mock_settings):
        client = TestClient(app)
        resp = client.post("/experiments/run", json={"code": "x = 1"})
    assert resp.status_code == 403


def test_49_02_04_returns_413_when_code_too_large():
    """Returns 413 when code exceeds max size."""
    mock_settings = MagicMock()
    mock_settings.experiment_enabled = True
    mock_settings.experiment_max_code_size = 10

    with patch("backend.api.routes.experiments.get_settings", return_value=mock_settings):
        client = TestClient(app)
        resp = client.post("/experiments/run", json={"code": "x" * 100})
    assert resp.status_code == 400  # BadRequestError from size check

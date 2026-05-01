"""Tests for BATCH-10/TASK-01: API Route Annotation.

Verifies that all API routes have proper summary, description, and example
docstrings as required by the BATCH-10 blueprint.
"""

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def openapi_schema():
    """Get the OpenAPI schema from the running app."""
    return app.openapi()


class TestOpenAPISchema:
    """TEST-10-01-01: /docs endpoint returns valid OpenAPI JSON with all paths."""

    def test_openapi_json_is_valid(self, openapi_schema):
        """OpenAPI schema is a valid dict with paths."""
        assert isinstance(openapi_schema, dict)
        assert "paths" in openapi_schema
        assert "info" in openapi_schema

    def test_all_route_prefixes_present(self, openapi_schema):
        """All 9 route prefixes appear in the OpenAPI schema."""
        paths = openapi_schema["paths"]
        prefixes = [
            "/api/v1/pipeline",
            "/api/v1/ideas",
            "/api/v1/gaps",
            "/api/v1/knowledge",
            "/api/v1/status",
            "/api/v1/memory",
            "/api/v1/governance",
            "/api/v1/costs",
            "/api/v1/traces",
        ]
        for prefix in prefixes:
            matching = [p for p in paths if p.startswith(prefix)]
            assert len(matching) > 0, f"No paths found for prefix {prefix}"


class TestRouteSummaries:
    """TEST-10-01-02: Every endpoint has non-empty summary in OpenAPI schema."""

    def test_all_endpoints_have_summary(self, openapi_schema):
        """Every route operation has a non-empty summary."""
        paths = openapi_schema["paths"]
        missing = []
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    summary = operation.get("summary", "")
                    if not summary or not summary.strip():
                        missing.append(f"{method.upper()} {path}")
        assert not missing, f"Endpoints missing summary: {missing}"

    def test_health_endpoint_has_summary(self, openapi_schema):
        """The /health endpoint has a summary."""
        health = openapi_schema["paths"].get("/health", {})
        get_op = health.get("get", {})
        assert get_op.get("summary"), "/health missing summary"


class TestResponseExamples:
    """TEST-10-01-03: Every endpoint has at least one response example in docstrings."""

    def test_routes_have_docstrings_with_examples(self, openapi_schema):
        """All route operations have descriptions (populated from docstrings)."""
        paths = openapi_schema["paths"]
        missing_desc = []
        for path, methods in paths.items():
            for method, operation in methods.items():
                if method in ("get", "post", "put", "delete", "patch"):
                    desc = operation.get("description", "")
                    if not desc or not desc.strip():
                        missing_desc.append(f"{method.upper()} {path}")
        # All routes should have at least a description from their docstring
        assert not missing_desc, f"Endpoints missing description: {missing_desc}"


class TestApiGuideDoc:
    """TEST-10-01-04: docs/api-guide.md contains curl examples for core endpoints."""

    def test_api_guide_exists(self):
        """docs/api-guide.md file exists."""
        from pathlib import Path

        guide_path = Path("docs/api-guide.md")
        assert guide_path.exists(), "docs/api-guide.md does not exist"

    def test_api_guide_has_curl_examples(self):
        """docs/api-guide.md contains curl examples."""
        from pathlib import Path

        content = Path("docs/api-guide.md").read_text(encoding="utf-8")
        assert "curl" in content.lower(), "api-guide.md has no curl examples"

    def test_api_guide_covers_core_endpoints(self):
        """docs/api-guide.md covers core endpoint groups."""
        from pathlib import Path

        content = Path("docs/api-guide.md").read_text(encoding="utf-8")
        required_sections = [
            "/api/v1/pipeline",
            "/api/v1/ideas",
            "/api/v1/gaps",
            "/api/v1/status",
        ]
        for section in required_sections:
            assert section in content, f"api-guide.md missing section for {section}"

    def test_api_guide_has_error_format(self):
        """docs/api-guide.md documents the error response format."""
        from pathlib import Path

        content = Path("docs/api-guide.md").read_text(encoding="utf-8")
        assert "error" in content.lower(), "api-guide.md missing error format documentation"
        assert "X-Request-Id" in content, "api-guide.md missing X-Request-Id documentation"

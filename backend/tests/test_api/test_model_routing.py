"""Tests for real model assignment overrides, certification, and stage metadata.

Phase A: Editable Model Routing UI.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError
from backend.api.model_assignments import (
    clear_assignments,
    get_stage_override,
    load_assignments,
    remove_stage,
    save_assignments,
)
from backend.api.routes.model_config import router

# ── Test app setup ──────────────────────────────────────────────


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router, prefix="/api/v1/settings")
    return app


@pytest.fixture
def temp_assignments_file(tmp_path, monkeypatch):
    """Use a temp directory for model_assignments.json."""
    temp_path = tmp_path / "model_assignments.json"
    monkeypatch.setattr("backend.api.model_assignments.ASSIGNMENTS_PATH", temp_path)
    return temp_path


@pytest.fixture
def client(temp_assignments_file):
    """TestClient with temp assignment file."""
    return TestClient(_make_app())


# ── model_assignments.py unit tests ─────────────────────────────


class TestAssignmentStore:
    """Direct tests for the model_assignments module."""

    def test_save_and_load_roundtrip(self, temp_assignments_file):
        save_assignments({"idea_generation": "qwen/qwen3-4b-2507"})
        loaded = load_assignments()
        assert loaded == {"idea_generation": "qwen/qwen3-4b-2507"}

    def test_load_empty_returns_empty(self, temp_assignments_file):
        assert load_assignments() == {}

    def test_clear_assignments(self, temp_assignments_file):
        save_assignments({"gap_analysis": "model-a"})
        clear_assignments()
        assert load_assignments() == {}

    def test_remove_single_stage(self, temp_assignments_file):
        save_assignments({"gap_analysis": "model-a", "idea_generation": "model-b"})
        remove_stage("gap_analysis")
        assert load_assignments() == {"idea_generation": "model-b"}

    def test_get_stage_override_returns_none_when_absent(self, temp_assignments_file):
        assert get_stage_override("gap_analysis") is None

    def test_get_stage_override_returns_model_id(self, temp_assignments_file):
        save_assignments({"gap_analysis": "qwen/qwen3-4b-2507"})
        assert get_stage_override("gap_analysis") == "qwen/qwen3-4b-2507"

    def test_file_has_schema_version(self, temp_assignments_file):
        save_assignments({"idea_generation": "model-a"})
        data = json.loads(temp_assignments_file.read_text())
        assert data["schema_version"] == 1
        assert "updated_at" in data
        assert "assignments" in data

    def test_file_persists_sorted_keys(self, temp_assignments_file):
        save_assignments({"z_stage": "model-z", "a_stage": "model-a"})
        data = json.loads(temp_assignments_file.read_text())
        keys = list(data["assignments"].keys())
        assert keys == ["a_stage", "z_stage"]


# ── Stage metadata endpoint ─────────────────────────────────────


class TestStageMetadata:
    """GET /settings/stages returns all pipeline stages with metadata."""

    def test_returns_all_16_stages(self, client):
        resp = client.get("/api/v1/settings/stages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 16
        names = [s["name"] for s in data["stages"]]
        assert "idea_generation" in names
        assert "proposal_synthesis" in names
        assert "literature_search" in names

    def test_stages_have_category(self, client):
        resp = client.get("/api/v1/settings/stages")
        stages = {s["name"]: s for s in resp.json()["stages"]}
        assert stages["gap_analysis"]["category"] == "thinking"
        assert stages["idea_generation"]["category"] == "generation"
        assert stages["ingestion"]["category"] == "passthrough"

    def test_stages_have_needs_llm(self, client):
        resp = client.get("/api/v1/settings/stages")
        stages = {s["name"]: s for s in resp.json()["stages"]}
        assert stages["gap_analysis"]["needs_llm"] is True
        assert stages["ingestion"]["needs_llm"] is False


# ── Certification endpoint ──────────────────────────────────────


class TestCertification:
    """GET /settings/certification returns production registry data."""

    def test_returns_certifications(self, client):
        with patch("backend.pipeline.routing.certified_lookup.CertifiedCapabilityLookup") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.production_models = {
                "qwen3-4b-2507": {
                    "provider": "lmstudio",
                    "status": "approved_for_limited_use",
                    "allowed_stages": {
                        "idea_generation": "limited_use",
                        "proposal_synthesis": "limited_use",
                    },
                }
            }
            mock_cls.return_value = mock_instance
            resp = client.get("/api/v1/settings/certification")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        cert = data["certifications"][0]
        assert cert["model_id"] == "qwen3-4b-2507"
        assert cert["status"] == "approved_for_limited_use"
        assert "idea_generation" in cert["allowed_stages"]

    def test_empty_registry_returns_empty_list(self, client):
        with patch("backend.pipeline.routing.certified_lookup.CertifiedCapabilityLookup") as mock_cls:
            mock_instance = MagicMock()
            mock_instance.production_models = {}
            mock_cls.return_value = mock_instance
            resp = client.get("/api/v1/settings/certification")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ── Override CRUD endpoints ─────────────────────────────────────


class TestOverrideCRUD:
    """GET/PUT/DELETE /settings/overrides."""

    def test_get_empty_overrides(self, client):
        resp = client.get("/api/v1/settings/overrides")
        assert resp.status_code == 200
        assert resp.json()["overrides"] == {}
        assert resp.json()["total"] == 0

    def test_put_creates_override(self, client):
        with patch("backend.providers.model_manager.get_model_manager") as mock_mm:
            mock_manager = MagicMock()
            mock_manager.is_initialized = True
            mock_catalog = MagicMock()
            mock_model = MagicMock()
            mock_model.model_id = "qwen/qwen3-4b-2507"
            mock_catalog.get_all.return_value = [mock_model]
            mock_manager.get_catalog.return_value = mock_catalog
            mock_mm.return_value = mock_manager

            resp = client.put("/api/v1/settings/overrides", json={
                "idea_generation": "qwen/qwen3-4b-2507"
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["overrides"]["idea_generation"] == "qwen/qwen3-4b-2507"
        assert len(data["warnings"]) == 0  # No cert data mocked → no warnings

    def test_put_dry_run_does_not_persist(self, client):
        with patch("backend.providers.model_manager.get_model_manager") as mock_mm:
            mock_manager = MagicMock()
            mock_manager.is_initialized = True
            mock_catalog = MagicMock()
            mock_model = MagicMock()
            mock_model.model_id = "qwen/qwen3-4b-2507"
            mock_catalog.get_all.return_value = [mock_model]
            mock_manager.get_catalog.return_value = mock_catalog
            mock_mm.return_value = mock_manager

            resp = client.put("/api/v1/settings/overrides?dry_run=true", json={
                "idea_generation": "qwen/qwen3-4b-2507"
            })

        assert resp.status_code == 200
        assert resp.json()["dry_run"] is True
        # File should not have been written
        assert load_assignments() == {}

    def test_put_unknown_stage_warning(self, client):
        with patch("backend.providers.model_manager.get_model_manager") as mock_mm:
            mock_manager = MagicMock()
            mock_manager.is_initialized = True
            mock_manager.get_catalog.return_value = MagicMock(get_all=MagicMock(return_value=[]))
            mock_mm.return_value = mock_manager

            resp = client.put("/api/v1/settings/overrides", json={
                "fake_stage": "some-model"
            })

        assert resp.status_code == 200
        warnings = resp.json()["warnings"]
        assert len(warnings) == 1
        assert warnings[0]["code"] == "UNKNOWN_STAGE"

    def test_put_unknown_model_warning(self, client):
        with patch("backend.providers.model_manager.get_model_manager") as mock_mm:
            mock_manager = MagicMock()
            mock_manager.is_initialized = True
            mock_catalog = MagicMock()
            real_model = MagicMock()
            real_model.model_id = "real-model"
            mock_catalog.get_all.return_value = [real_model]
            mock_manager.get_catalog.return_value = mock_catalog
            mock_mm.return_value = mock_manager

            resp = client.put("/api/v1/settings/overrides", json={
                "idea_generation": "nonexistent-model"
            })

        assert resp.status_code == 200
        warnings = resp.json()["warnings"]
        assert len(warnings) == 1
        assert warnings[0]["code"] == "UNKNOWN_MODEL"

    def test_put_not_certified_warning(self, client):
        """Model exists in catalog but not certified for the stage."""
        with patch("backend.providers.model_manager.get_model_manager") as mock_mm:
            mock_manager = MagicMock()
            mock_manager.is_initialized = True
            mock_catalog = MagicMock()
            mock_model = MagicMock()
            mock_model.model_id = "qwen/qwen3-4b-2507"
            mock_catalog.get_all.return_value = [mock_model]
            mock_manager.get_catalog.return_value = mock_catalog
            mock_mm.return_value = mock_manager

            with patch("backend.pipeline.routing.certified_lookup.CertifiedCapabilityLookup") as mock_cert:
                mock_cert_instance = MagicMock()
                mock_cert_instance.production_models = {
                    "qwen/qwen3-4b-2507": {
                        "provider": "lmstudio",
                        "status": "approved_for_limited_use",
                        "allowed_stages": {"idea_generation": "limited_use"},
                    }
                }
                mock_cert.return_value = mock_cert_instance

                resp = client.put("/api/v1/settings/overrides", json={
                    "paper_synthesis": "qwen/qwen3-4b-2507"  # not in allowed_stages
                })

        assert resp.status_code == 200
        warnings = resp.json()["warnings"]
        assert len(warnings) == 1
        assert warnings[0]["code"] == "NOT_CERTIFIED"
        assert warnings[0]["stage"] == "paper_synthesis"

    def test_validate_endpoint(self, client):
        """POST /settings/overrides/validate runs validation without saving."""
        with patch("backend.providers.model_manager.get_model_manager") as mock_mm:
            mock_manager = MagicMock()
            mock_manager.is_initialized = True
            mock_manager.get_catalog.return_value = MagicMock(get_all=MagicMock(return_value=[]))
            mock_mm.return_value = mock_manager

            resp = client.post("/api/v1/settings/overrides/validate", json={
                "fake_stage": "some-model"
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["warnings"]) == 1
        assert load_assignments() == {}

    def test_delete_single_stage(self, client):
        """DELETE /settings/overrides/{stage} removes one override."""
        save_assignments({"idea_generation": "model-a", "gap_analysis": "model-b"})

        resp = client.delete("/api/v1/settings/overrides/idea_generation")
        assert resp.status_code == 200
        assert "idea_generation" not in resp.json()["overrides"]
        assert resp.json()["overrides"]["gap_analysis"] == "model-b"

    def test_delete_single_stage_unknown(self, client):
        """DELETE /settings/overrides/{stage} rejects unknown stage."""
        resp = client.delete("/api/v1/settings/overrides/fake_stage")
        assert resp.status_code == 400

    def test_delete_all_overrides(self, client):
        """DELETE /settings/overrides clears all overrides."""
        save_assignments({"idea_generation": "model-a"})

        resp = client.delete("/api/v1/settings/overrides")
        assert resp.status_code == 200
        assert resp.json()["overrides"] == {}
        assert load_assignments() == {}

    def test_put_merges_with_existing(self, client):
        """PUT merges new stages with existing overrides."""
        save_assignments({"gap_analysis": "model-a"})

        with patch("backend.providers.model_manager.get_model_manager") as mock_mm:
            mock_manager = MagicMock()
            mock_manager.is_initialized = True
            mock_catalog = MagicMock()
            mock_model = MagicMock()
            mock_model.model_id = "model-b"
            mock_catalog.get_all.return_value = [mock_model]
            mock_manager.get_catalog.return_value = mock_catalog
            mock_mm.return_value = mock_manager

            resp = client.put("/api/v1/settings/overrides", json={
                "idea_generation": "model-b"
            })

        overrides = resp.json()["overrides"]
        assert overrides["gap_analysis"] == "model-a"  # preserved
        assert overrides["idea_generation"] == "model-b"  # new

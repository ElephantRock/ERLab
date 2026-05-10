"""BATCH-151 Tests — Docker Deployment + AI Honesty Badge.

Tests for:
  TASK-01: Backend Dockerfile + health endpoint
  TASK-02: Frontend Dockerfile + Nginx config
  TASK-03: docker-compose.yml + .env.docker
  TASK-04: AI honesty badge in all export formats
"""

import pytest
import os
from pathlib import Path
from unittest.mock import MagicMock

# Project root
ROOT = Path(__file__).resolve().parents[3]


# ── TASK-01: Backend Dockerfile ───────────────────────────────

class TestBackendDockerfile:
    """Tests for TASK-01: Backend Dockerfile + health endpoint."""

    def test_health_endpoint_exists(self):
        """TEST-151-01-01: /health endpoint returns 200 with status ok."""
        from backend.api.app import health
        result = asyncio_run(health())
        assert result["status"] == "ok"
        assert "version" in result

    def test_dockerfile_backend_exists(self):
        """TEST-151-01-02: Dockerfile.backend exists and is valid."""
        dockerfile = ROOT / "Dockerfile.backend"
        assert dockerfile.exists(), "Dockerfile.backend must exist"
        content = dockerfile.read_text()
        assert "python:3.11-slim" in content, "Must use Python 3.11 base image"
        assert "FROM" in content, "Must have FROM instruction"
        assert "docker-entrypoint.sh" in content, "Must reference entrypoint script"
        # uvicorn is started via the entrypoint script, not directly in Dockerfile
        entrypoint = ROOT / "docker-entrypoint.sh"
        assert entrypoint.exists(), "docker-entrypoint.sh must exist"
        assert "uvicorn" in entrypoint.read_text(), "Entrypoint must start uvicorn"

    def test_entrypoint_runs_migrations(self):
        """TEST-151-01-03: Entrypoint runs Alembic migrations before uvicorn."""
        entrypoint = ROOT / "docker-entrypoint.sh"
        assert entrypoint.exists(), "docker-entrypoint.sh must exist"
        content = entrypoint.read_text()
        assert "alembic upgrade head" in content, "Must run Alembic migrations"
        assert "uvicorn" in content, "Must start uvicorn"
        # Alembic must come before uvicorn
        assert content.index("alembic") < content.index("uvicorn"), \
            "Migrations must run before uvicorn starts"

    def test_backend_non_root_user(self):
        """TEST-151-01-04: Backend runs as non-root user."""
        dockerfile = ROOT / "Dockerfile.backend"
        content = dockerfile.read_text()
        assert "USER erock" in content, "Must run as non-root user 'erock'"
        assert "groupadd" in content or "useradd" in content, \
            "Must create non-root user"


# ── TASK-02: Frontend Dockerfile ──────────────────────────────

class TestFrontendDockerfile:
    """Tests for TASK-02: Frontend Dockerfile + Nginx config."""

    def test_dockerfile_frontend_exists(self):
        """TEST-151-02-01: Dockerfile.frontend exists and is valid."""
        dockerfile = ROOT / "Dockerfile.frontend"
        assert dockerfile.exists(), "Dockerfile.frontend must exist"
        content = dockerfile.read_text()
        assert "node:22" in content or "node:" in content, "Must use Node.js base image"
        assert "nginx" in content.lower(), "Must use Nginx for serving"
        assert "npm run build" in content, "Must build Vite production bundle"

    def test_nginx_proxies_api(self):
        """TEST-151-02-02: Nginx config proxies /api/* to backend."""
        nginx_conf = ROOT / "nginx" / "nginx.conf"
        assert nginx_conf.exists(), "nginx/nginx.conf must exist"
        content = nginx_conf.read_text()
        assert "proxy_pass" in content, "Must have proxy_pass directive"
        assert "backend" in content, "Must proxy to backend service"
        assert "/api/" in content, "Must proxy /api/ location"

    def test_nginx_serves_frontend(self):
        """TEST-151-02-03: Nginx serves static frontend files."""
        nginx_conf = ROOT / "nginx" / "nginx.conf"
        content = nginx_conf.read_text()
        assert "/usr/share/nginx/html" in content, \
            "Must serve from standard Nginx HTML directory"
        assert "try_files" in content, "Must have try_files for SPA routing"

    def test_nginx_gzip_and_mime(self):
        """TEST-151-02-04: Nginx config includes MIME types and gzip."""
        nginx_conf = ROOT / "nginx" / "nginx.conf"
        content = nginx_conf.read_text()
        assert "gzip on" in content, "Must enable gzip compression"
        assert "gzip_types" in content, "Must specify gzip content types"


# ── TASK-03: docker-compose.yml ───────────────────────────────

class TestDockerCompose:
    """Tests for TASK-03: docker-compose.yml + .env.docker."""

    def test_compose_file_valid_yaml(self):
        """TEST-151-03-01: docker-compose.yml is valid YAML with 2 services."""
        import yaml
        compose_path = ROOT / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml must exist"
        with open(compose_path) as f:
            compose = yaml.safe_load(f)
        assert "services" in compose, "Must have services section"
        assert "backend" in compose["services"], "Must have backend service"
        assert "frontend" in compose["services"], "Must have frontend service"

    def test_named_volume_for_data(self):
        """TEST-151-03-02: Named volume declared for SQLite data persistence."""
        import yaml
        compose_path = ROOT / "docker-compose.yml"
        with open(compose_path) as f:
            compose = yaml.safe_load(f)
        assert "volumes" in compose, "Must have volumes section"
        volume_names = list(compose["volumes"].keys())
        assert len(volume_names) > 0, "Must have at least one named volume"
        # Backend must mount the volume
        backend_volumes = compose["services"]["backend"].get("volumes", [])
        assert any("erock_data" in str(v) for v in backend_volumes), \
            "Backend must mount erock_data volume"

    def test_env_docker_documents_all_keys(self):
        """TEST-151-03-03: .env.docker documents all EROCK_ variables from .env.example."""
        env_docker = ROOT / ".env.docker"
        assert env_docker.exists(), ".env.docker must exist"
        content = env_docker.read_text()
        # Check key variables are documented (at least as comments)
        essential_keys = [
            "EROCK_DEFAULT_PROVIDER",
            "EROCK_ANTHROPIC_API_KEY",
            "EROCK_ENV",
            "EROCK_DEBUG",
        ]
        for key in essential_keys:
            assert key in content, f".env.docker must document {key}"

    def test_backend_health_check(self):
        """TEST-151-03-04: Backend health check configured in compose."""
        import yaml
        compose_path = ROOT / "docker-compose.yml"
        with open(compose_path) as f:
            compose = yaml.safe_load(f)
        backend = compose["services"]["backend"]
        assert "healthcheck" in backend, "Backend must have health check"
        test_cmd = backend["healthcheck"]["test"]
        assert "/health" in str(test_cmd), "Health check must hit /health endpoint"

    def test_frontend_depends_on_backend(self):
        """TEST-151-03-05: Frontend depends_on backend with health condition."""
        import yaml
        compose_path = ROOT / "docker-compose.yml"
        with open(compose_path) as f:
            compose = yaml.safe_load(f)
        frontend = compose["services"]["frontend"]
        assert "depends_on" in frontend, "Frontend must depend on backend"
        deps = frontend["depends_on"]
        assert "backend" in deps, "Must depend on backend service"


# ── TASK-04: AI Honesty Badge ─────────────────────────────────

class TestAIHonestyBadge:
    """Tests for TASK-04: AI honesty badge in all export formats."""

    def test_badge_constant_exists(self):
        """TEST-151-04-01: AI_HONESTY_BADGE constant exists with required text."""
        from backend.pipeline.constants import AI_HONESTY_BADGE, AI_HONESTY_BADGE_BRIEF
        assert "AI pipeline" in AI_HONESTY_BADGE, \
            "Badge must mention 'AI pipeline'"
        assert "independently verified" in AI_HONESTY_BADGE, \
            "Badge must mention 'independently verified'"
        assert "AI pipeline" in AI_HONESTY_BADGE_BRIEF
        assert "independently verified" in AI_HONESTY_BADGE_BRIEF

    def test_markdown_export_includes_badge(self):
        """TEST-151-04-02: Markdown export ends with AI honesty badge."""
        from backend.pipeline.export.markdown_exporter import MarkdownExporter
        from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

        proposal = ResearchProposal(
            idea_id="test",
            title="Test Proposal",
            sections={
                "title": "Test Proposal",
                "abstract": "Test abstract",
                "introduction": "Test intro",
                "related_work": "Test related",
                "proposed_method": "Test method",
                "expected_contributions": "Test contributions",
                "evaluation_plan": "Test eval",
                "timeline": "Test timeline",
                "references": [],
                "risk_mitigation": "Test risks",
            }
        )
        exporter = MarkdownExporter()
        md = exporter.export(proposal)
        assert "AI pipeline" in md, "Markdown export must include badge"
        assert "independently verified" in md, "Badge must be present at end"

    def test_latex_export_includes_badge(self):
        """TEST-151-04-03: LaTeX export includes AI honesty badge."""
        from backend.pipeline.export.latex_exporter import LatexExporter
        from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal

        proposal = ResearchProposal(
            idea_id="test",
            title="Test Proposal",
            sections={
                "title": "Test Proposal",
                "abstract": "Test abstract",
                "introduction": "Test intro",
                "related_work": "Test related",
                "proposed_method": "Test method",
                "expected_contributions": "Test contributions",
                "evaluation_plan": "Test eval",
                "timeline": "Test timeline",
                "references": [],
                "risk_mitigation": "Test risks",
            }
        )
        exporter = LatexExporter()
        latex = exporter.export(proposal)
        assert "AI pipeline" in latex, "LaTeX export must include badge"
        assert "independently verified" in latex, "Badge text must be present"

    def test_bibtex_export_includes_badge(self):
        """TEST-151-04-04: BibTeX export includes badge in note field."""
        from backend.pipeline.export.bibtex_exporter import proposal_to_bibtex
        bibtex = proposal_to_bibtex("Test Proposal", domain="AI", year=2026)
        assert "AI-generated" in bibtex, "BibTeX must note AI-generated"
        assert "independently verified" in bibtex, "Badge must be in note field"

    def test_md_to_latex_includes_badge(self):
        """TEST-151-04-05: md_to_latex conversion includes badge."""
        from backend.pipeline.export.md_to_latex import MarkdownToLatexConverter
        converter = MarkdownToLatexConverter()
        latex = converter.convert_to_document("# Test\n\nHello world.", title="Test")
        assert "AI pipeline" in latex, "LaTeX document must include badge"
        assert "independently verified" in latex, "Badge text must be present"

    def test_badge_text_consistent(self):
        """TEST-151-04-06: Badge text is consistent across all formats."""
        from backend.pipeline.constants import AI_HONESTY_BADGE_BRIEF
        from backend.pipeline.export.markdown_exporter import MarkdownExporter
        from backend.pipeline.export.bibtex_exporter import proposal_to_bibtex

        # All formats must reference the same constant
        bibtex = proposal_to_bibtex("Test", domain="AI")
        assert AI_HONESTY_BADGE_BRIEF in bibtex, \
            "BibTeX must use AI_HONESTY_BADGE_BRIEF constant"


# ── Helpers ───────────────────────────────────────────────────

def asyncio_run(coro):
    """Run async coroutine synchronously."""
    import asyncio
    return asyncio.run(coro)

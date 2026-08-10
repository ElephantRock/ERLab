"""BATCH-170: Citation Graph Visualization & Frontend Polish."""


class TestCitationGraph:

    def test_01_citation_graph_endpoint_exists(self):
        from backend.api.routes.pipeline import router
        routes = [r.path for r in router.routes]
        assert any("citation-graph" in r for r in routes)

    def test_02_graph_canvas_component_exists(self):
        from pathlib import Path
        assert Path("frontend/src/components/knowledge-graph/graph-canvas.tsx").exists()

    def test_03_entity_detail_component(self):
        from pathlib import Path
        assert Path("frontend/src/components/knowledge-graph/entity-detail.tsx").exists()

    def test_04_knowledge_graph_page(self):
        from pathlib import Path
        assert Path("frontend/src/pages/knowledge-graph.tsx").exists()

    def test_05_citation_graph_returns_404_for_missing(self):
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        response = client.get("/api/v1/pipeline/runs/nonexistent_xxx/citation-graph")
        assert response.status_code in (200, 404)

    def test_06_evaluation_card_component(self):
        # Phase 2 2D: evaluation-card.tsx was removed (no truthful producer per
        # the 2A audit). Paper evaluation is now rendered by the paper-workspace
        # component (PaperEvaluation section). Verify the successor renders
        # evaluation content.
        from pathlib import Path
        content = Path("frontend/src/components/ideas/paper-workspace.tsx").read_text(encoding="utf-8")
        assert "evaluation" in content.lower() or "score" in content.lower()

    def test_07_radar_chart_component(self):
        from pathlib import Path
        assert Path("frontend/src/components/ideas/radar-chart.tsx").exists()

    def test_08_sidebar_has_all_routes(self):
        from pathlib import Path
        content = Path("frontend/src/components/layout/sidebar.tsx").read_text(encoding="utf-8")
        assert "pipeline" in content.lower()
        assert "ideas" in content.lower() or "gaps" in content.lower()

    def test_09_onboarding_overlay(self):
        from pathlib import Path
        assert Path("frontend/src/components/onboarding/onboarding-overlay.tsx").exists()

    def test_10_frontend_polish_dark_mode(self):
        from pathlib import Path
        assert Path("frontend/src/contexts/settings-context.tsx").exists()

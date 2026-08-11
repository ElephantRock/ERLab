"""BATCH-158: Knowledge Library Persistence — Cross-run memory.

TASK-01: Post-run indexing in ExportStage (7 tests)
TASK-02: Pre-run knowledge query in LiteratureSearchStage (5 tests)
TASK-03: Knowledge query API endpoint (2 tests)
"""
import json
import os
import tempfile
from unittest.mock import MagicMock

# ─── Helpers ────────────────────────────────────────────────

def _make_library(db_path=None):
    from backend.pipeline.knowledge.library import KnowledgeLibrary
    if db_path is None:
        tmp = tempfile.mktemp(suffix=".db")
        lib = KnowledgeLibrary(db_path=tmp)
        return lib, tmp
    return KnowledgeLibrary(db_path=db_path), db_path


# ─── TASK-01: Post-run indexing ─────────────────────────────

class TestPostRunIndexing:

    def test_01_knowledge_library_add_paper(self):
        from backend.pipeline.knowledge.library import LibraryEntry
        lib, tmp = _make_library()
        try:
            entry = LibraryEntry(
                entry_type="paper",
                domain="AI/NLP",
                title="Attention Is All You Need",
                content=json.dumps({"doi": "10.5555/1234", "year": 2017}),
            )
            assert lib.add(entry) is True
            assert lib.count(domain="AI/NLP") == 1
        finally:
            lib.close()
            os.unlink(tmp)

    def test_02_knowledge_library_dedup(self):
        from backend.pipeline.knowledge.library import LibraryEntry
        lib, tmp = _make_library()
        try:
            entry = LibraryEntry(entry_type="paper", domain="AI", title="Test Paper", content="{}")
            assert lib.add(entry) is True
            entry2 = LibraryEntry(entry_type="paper", domain="AI", title="Test Paper", content="{}")
            assert lib.add(entry2) is False  # duplicate
            assert lib.count(domain="AI") == 1
        finally:
            lib.close()
            os.unlink(tmp)

    def test_03_library_indexer_index_run(self):
        from backend.pipeline.knowledge.library_indexer import LibraryIndexer
        lib, tmp = _make_library()
        try:
            indexer = LibraryIndexer(lib)
            paper = MagicMock(title="Test Paper", doi="10.1234/test", year=2024, abstract="Abstract", authors=[])
            gap = MagicMock(title="Test Gap", description="A gap")
            idea = MagicMock(title="Test Idea", description="An idea", novelty_score=0.9)
            counts = indexer.index_run("AI/NLP", "run_test", papers=[paper], gaps=[gap], ideas=[idea])
            assert counts["papers"] == 1
            assert counts["gaps"] == 1
            assert counts["ideas"] == 1
            assert counts["total"] == 3
        finally:
            lib.close()
            os.unlink(tmp)

    def test_04_knowledge_integration_service(self):
        from backend.pipeline.knowledge.integration import KnowledgeIntegrationService
        tmpdir = tempfile.mkdtemp()
        tmp_lib = os.path.join(tmpdir, "library.db")
        tmp_err = os.path.join(tmpdir, "errors.db")
        service = KnowledgeIntegrationService(
            library_dir=tmpdir,
            error_db_path=tmp_err,
        )
        try:
            paper = MagicMock(title="Integration Paper", doi="", year=2024, abstract="Test", authors=[])
            counts = service.index_run_results("AI", papers=[paper], run_id="run_1")
            assert counts["papers"] == 1
            summary = service.query_existing_knowledge("AI")
            assert summary["has_knowledge"] is True
            assert summary["existing_papers"] == 1
        finally:
            service.close()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_05_query_by_domain(self):
        from backend.pipeline.knowledge.library import LibraryEntry
        lib, tmp = _make_library()
        try:
            lib.add(LibraryEntry(entry_type="paper", domain="AI", title="AI Paper", content="{}"))
            lib.add(LibraryEntry(entry_type="paper", domain="Bio", title="Bio Paper", content="{}"))
            assert lib.count(domain="AI") == 1
            assert lib.count(domain="Bio") == 1
            assert lib.count() == 2
        finally:
            lib.close()
            os.unlink(tmp)

    def test_06_count_by_type(self):
        from backend.pipeline.knowledge.library import LibraryEntry
        lib, tmp = _make_library()
        try:
            lib.add(LibraryEntry(entry_type="paper", domain="AI", title="P1", content="{}"))
            lib.add(LibraryEntry(entry_type="gap", domain="AI", title="G1", content="{}"))
            lib.add(LibraryEntry(entry_type="idea", domain="AI", title="I1", content="{}"))
            assert lib.count(entry_type="paper") == 1
            assert lib.count(entry_type="gap") == 1
            assert lib.count(entry_type="idea") == 1
        finally:
            lib.close()
            os.unlink(tmp)

    def test_07_add_papers_bulk(self):
        lib, tmp = _make_library()
        try:
            papers = [
                MagicMock(title=f"Paper {i}", doi=f"10.1/{i}", year=2024, abstract=f"Abstract {i}", authors=[])
                for i in range(5)
            ]
            added = lib.add_papers(papers, "AI", "run_bulk")
            assert added == 5
            assert lib.count(domain="AI") == 5
        finally:
            lib.close()
            os.unlink(tmp)


# ─── TASK-02: Pre-run knowledge query ──────────────────────

class TestPreRunKnowledge:

    def test_08_indexer_get_existing_papers(self):
        from backend.pipeline.knowledge.library_indexer import LibraryIndexer
        lib, tmp = _make_library()
        try:
            indexer = LibraryIndexer(lib)
            paper = MagicMock(title="Existing Paper", doi="", year=2024, abstract="Test", authors=[])
            indexer.index_run("AI/NLP", "run_1", papers=[paper])
            existing = indexer.get_existing_papers("AI/NLP")
            assert len(existing) == 1
            assert existing[0]["title"] == "Existing Paper"
        finally:
            lib.close()
            os.unlink(tmp)

    def test_09_indexer_get_existing_gaps(self):
        from backend.pipeline.knowledge.library_indexer import LibraryIndexer
        lib, tmp = _make_library()
        try:
            indexer = LibraryIndexer(lib)
            gap = MagicMock(title="Existing Gap", description="A gap")
            indexer.index_run("AI/NLP", "run_1", gaps=[gap])
            existing = indexer.get_existing_gaps("AI/NLP")
            assert len(existing) == 1
        finally:
            lib.close()
            os.unlink(tmp)

    def test_10_empty_domain_returns_empty(self):
        from backend.pipeline.knowledge.library_indexer import LibraryIndexer
        lib, tmp = _make_library()
        try:
            indexer = LibraryIndexer(lib)
            existing = indexer.get_existing_papers("nonexistent_domain")
            assert existing == []
        finally:
            lib.close()
            os.unlink(tmp)

    def test_11_cross_domain_isolation(self):
        from backend.pipeline.knowledge.library_indexer import LibraryIndexer
        lib, tmp = _make_library()
        try:
            indexer = LibraryIndexer(lib)
            p1 = MagicMock(title="AI Paper", doi="", year=2024, abstract="", authors=[])
            indexer.index_run("AI", "run_1", papers=[p1])
            existing_bio = indexer.get_existing_papers("Biology")
            assert existing_bio == []
        finally:
            lib.close()
            os.unlink(tmp)

    def test_12_integration_service_failure_recording(self):
        from backend.pipeline.knowledge.integration import KnowledgeIntegrationService
        tmp_lib = tempfile.mktemp(suffix=".db")
        tmp_err = tempfile.mktemp(suffix=".db")
        service = KnowledgeIntegrationService(
            library_dir=os.path.dirname(tmp_lib),
            error_db_path=tmp_err,
        )
        try:
            service.record_failure("gap_analysis", "Low quality gaps", "Increase threshold")
            failures = service.get_past_failures(stage="gap_analysis")
            assert len(failures) >= 1
        finally:
            service.close()
            for f in [tmp_lib, tmp_err]:
                if os.path.exists(f):
                    os.unlink(f)


# ─── TASK-03: API Endpoint ─────────────────────────────────

class TestKnowledgeAPI:

    def test_13_knowledge_endpoint_exists(self):
        from backend.api.routes.search import router
        routes = [r.path for r in router.routes]
        assert any("knowledge" in r for r in routes)

    def test_14_knowledge_endpoint_returns_data(self):
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        response = client.get("/api/v1/search/knowledge/AI")
        assert response.status_code == 200
        data = response.json()
        assert "domain" in data
        assert "papers" in data
        assert "gaps" in data

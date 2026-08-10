"""Phase 4 / WP-4C tests — citation-map propagation through paper generation.

These tests pin the marker→source map that ``PaperSynthesisStage`` must now
freeze at synthesis time, persist, and expose to every downstream reader
(exports, Trust & Sources, the evaluation gate).

Required behavior under test:
  1. The ordered source list used to construct [SOURCE-N] is frozen and persisted.
  2. Markers emitted in the generated paper are scanned.
  3. Out-of-range or otherwise unknown markers are persisted as ``unmapped``.
  4. Identities are never reconstructed later through semantic matching.
"""

import re

from backend.pipeline.synthesis.paper_synthesizer import PaperSynthesisResult


def _scan_markers(paper_md: str) -> set[int]:
    """The same scan the synthesis stage must run on its generated paper."""
    return {int(n) for n in re.findall(r"\[SOURCE-(\d+)\]", paper_md)}


class TestSourceMapOnPaperSynthesisResult:
    """PaperSynthesisResult carries the frozen marker→source map."""

    def test_result_carries_source_map(self):
        """A result with a source map exposes marker_index + source identity."""
        result = PaperSynthesisResult(
            proposal_id=1,
            paper_markdown="# Paper\nUses [SOURCE-1] and [SOURCE-2].",
            word_count=5,
            venue="Generic",
            model_used="test",
            source_count=2,
            source_map=[
                {"marker_index": 1, "marker": "SOURCE-1", "source_id": "arxiv:111"},
                {"marker_index": 2, "marker": "SOURCE-2", "source_id": "arxiv:222"},
            ],
        )
        d = result.to_dict()
        assert "source_map" in d
        assert d["source_map"][0]["source_id"] == "arxiv:111"

    def test_result_without_source_map_defaults_empty(self):
        """Backward compat: a result constructed without a map has []."""
        result = PaperSynthesisResult(
            proposal_id=1, paper_markdown="x", word_count=1,
            venue="G", model_used="t", source_count=0,
        )
        assert result.source_map == []


class TestBuildSourceMap:
    """The function that freezes the ordered source list and scans the paper."""

    def test_in_range_markers_are_mapped(self):
        """Every [SOURCE-N] within the source list is mapped to its source_id."""
        from backend.pipeline.stages import PaperSynthesisStage

        source_ids = ["arxiv:111", "arxiv:222", "arxiv:333"]
        paper_md = "Body citing [SOURCE-1] then [SOURCE-3]."
        source_map = PaperSynthesisStage.build_source_map(source_ids, paper_md)

        by_index = {m["marker_index"]: m for m in source_map}
        assert by_index[1]["source_id"] == "arxiv:111"
        assert by_index[1]["mapping_status"] == "mapped"
        assert by_index[3]["source_id"] == "arxiv:333"
        assert by_index[3]["mapping_status"] == "mapped"
        # Marker 2 was not emitted but still appears as a mapped slot.
        assert by_index[2]["source_id"] == "arxiv:222"
        assert by_index[2]["mapping_status"] == "mapped"

    def test_out_of_range_markers_are_unmapped(self):
        """An emitted marker beyond the source list is explicitly unmapped."""
        from backend.pipeline.stages import PaperSynthesisStage

        source_ids = ["arxiv:111"]  # only SOURCE-1 exists
        paper_md = "Cites [SOURCE-1] and also [SOURCE-99]."
        source_map = PaperSynthesisStage.build_source_map(source_ids, paper_md)

        by_index = {m["marker_index"]: m for m in source_map}
        assert by_index[1]["mapping_status"] == "mapped"
        assert by_index[1]["source_id"] == "arxiv:111"
        # SOURCE-99 was emitted by the model but has no source.
        assert 99 in by_index
        assert by_index[99]["mapping_status"] == "unmapped"
        assert by_index[99]["source_id"] is None

    def test_no_semantic_reconstruction(self):
        """An unmapped marker is never assigned a guessed identity."""
        from backend.pipeline.stages import PaperSynthesisStage

        source_ids = ["arxiv:111"]
        paper_md = "[SOURCE-1] and [SOURCE-42]."
        source_map = PaperSynthesisStage.build_source_map(source_ids, paper_md)

        unmapped = [m for m in source_map if m["mapping_status"] == "unmapped"]
        assert len(unmapped) == 1
        # The unmapped marker carries NO source_id — identity is not guessed.
        assert unmapped[0]["source_id"] is None
        assert unmapped[0]["marker"] == "SOURCE-42"

    def test_marker_string_format(self):
        """Marker strings are the literal SOURCE-N form used in the paper."""
        from backend.pipeline.stages import PaperSynthesisStage

        source_map = PaperSynthesisStage.build_source_map(["x"], "[SOURCE-1]")
        assert source_map[0]["marker"] == "SOURCE-1"


class TestPersistSourceMarkersResolution:
    """The persistence helper resolves source_id → papers.id, downgrades misses."""

    def test_mapped_source_resolves_to_db_paper(self, tmp_path, monkeypatch):
        from contextlib import contextmanager

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from backend.db import crud
        from backend.db.database import Base
        from backend.db.models import Idea, PipelineRun, Proposal
        from backend.pipeline.persistence import PipelinePersistence

        engine = create_engine(f"sqlite:///{tmp_path}/m.db")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, expire_on_commit=False)

        @contextmanager
        def _sess():
            s = Session()
            try:
                yield s
            finally:
                s.close()

        # Seed a proposal + a paper with source_id "arxiv:111".
        with _sess() as s:
            run = PipelineRun(status="completed", provenance_version="provenance_v1")
            s.add(run); s.flush()
            idea = Idea(title="T", problem_statement="p", proposed_method="m", pipeline_run_id=run.id)
            s.add(idea); s.flush()
            prop = Proposal(idea_id=idea.id, content_md="# P")
            s.add(prop); s.flush()
            crud.add_paper(s, source_id="arxiv:111", source="arxiv", title="S1", doi="10.1/x")
            s.commit()
            prop_id = prop.id

        source_map = [
            {"marker_index": 1, "marker": "SOURCE-1", "source_id": "arxiv:111", "mapping_status": "mapped"},
            {"marker_index": 2, "marker": "SOURCE-2", "source_id": None, "mapping_status": "unmapped"},
        ]
        with _sess() as s:
            PipelinePersistence._persist_source_markers(s, prop_id, source_map)
            s.commit()
            markers = crud.get_source_markers_for_proposal(s, prop_id)
            # Access lazy-loaded relationship within the session scope.
            assert len(markers) == 2
            assert markers[0].mapping_status == "mapped"
            assert markers[0].source_paper_id is not None
            assert markers[0].source_paper.doi == "10.1/x"
            assert markers[1].mapping_status == "unmapped"
            assert markers[1].source_paper_id is None

    def test_unresolvable_source_downgrades_to_unmapped(self, tmp_path):
        from contextlib import contextmanager

        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        from backend.db import crud
        from backend.db.database import Base
        from backend.db.models import Idea, PipelineRun, Proposal
        from backend.pipeline.persistence import PipelinePersistence

        engine = create_engine(f"sqlite:///{tmp_path}/m2.db")
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine, expire_on_commit=False)

        @contextmanager
        def _sess():
            s = Session()
            try:
                yield s
            finally:
                s.close()

        with _sess() as s:
            run = PipelineRun(status="completed", provenance_version="provenance_v1")
            s.add(run); s.flush()
            idea = Idea(title="T", problem_statement="p", proposed_method="m", pipeline_run_id=run.id)
            s.add(idea); s.flush()
            prop = Proposal(idea_id=idea.id, content_md="# P")
            s.add(prop); s.flush()
            s.commit()
            prop_id = prop.id

        # A 'mapped' entry whose source_id is NOT in the papers table.
        source_map = [
            {"marker_index": 1, "marker": "SOURCE-1", "source_id": "ghost:999", "mapping_status": "mapped"},
        ]
        with _sess() as s:
            PipelinePersistence._persist_source_markers(s, prop_id, source_map)
            s.commit()
            markers = crud.get_source_markers_for_proposal(s, prop_id)

        assert len(markers) == 1
        # Downgraded to unmapped — never guessed, never dropped.
        assert markers[0].mapping_status == "unmapped"
        assert markers[0].source_paper_id is None

"""BATCH-161: Recursive Deep Research — Citation Tree Exploration.

TASK-01: CitationExplorer class (5 tests)
TASK-02: TreeExplorationResult model (4 tests)
TASK-03: Strategy preset wiring (3 tests)
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

# ─── TASK-01: CitationExplorer ──────────────────────────────

class TestCitationExplorer:

    def test_01_explore_with_no_sources(self):
        from backend.pipeline.literature.citation_explorer import CitationExplorer
        from backend.pipeline.literature.models import Paper

        explorer = CitationExplorer(s2_source=None, openalex_source=None)
        seed = Paper(id="test", source="test", title="Test Paper", abstract="")
        result = asyncio.run(explorer.explore([seed], max_depth=1, breadth=5))
        assert result.seed_papers == 1
        assert result.total_discovered == 0

    def test_02_explore_forward_citations(self):
        from backend.pipeline.literature.citation_explorer import CitationExplorer
        from backend.pipeline.literature.models import Paper

        mock_s2 = MagicMock()
        citing_paper = Paper(id="citing1", source="s2", title="Citing Paper", abstract="")
        mock_s2.get_citations = AsyncMock(return_value=[citing_paper])

        explorer = CitationExplorer(s2_source=mock_s2, openalex_source=None, cooldown=0)
        seed = Paper(id="seed1", source="test", title="Seed Paper", abstract="")
        result = asyncio.run(explorer.explore([seed], max_depth=1, breadth=5, direction="forward"))

        assert result.seed_papers == 1
        assert result.forward_papers == 1
        assert result.total_discovered == 1

    def test_03_explore_backward_references(self):
        from backend.pipeline.literature.citation_explorer import CitationExplorer
        from backend.pipeline.literature.models import Paper

        mock_s2 = MagicMock()
        ref_paper = Paper(id="ref1", source="s2", title="Referenced Paper", abstract="")
        mock_s2.get_references = AsyncMock(return_value=[ref_paper])

        explorer = CitationExplorer(s2_source=mock_s2, openalex_source=None, cooldown=0)
        seed = Paper(id="seed1", source="test", title="Seed Paper", abstract="")
        result = asyncio.run(explorer.explore([seed], max_depth=1, breadth=5, direction="backward"))

        assert result.backward_papers == 1
        assert result.total_discovered == 1

    def test_04_dedup_across_tree(self):
        from backend.pipeline.literature.citation_explorer import CitationExplorer
        from backend.pipeline.literature.models import Paper

        mock_s2 = MagicMock()
        dup_paper = Paper(id="dup1", source="s2", title="Duplicate Paper", abstract="")
        mock_s2.get_citations = AsyncMock(return_value=[dup_paper])
        mock_s2.get_references = AsyncMock(return_value=[dup_paper])

        explorer = CitationExplorer(s2_source=mock_s2, openalex_source=None, cooldown=0)
        seed = Paper(id="seed1", source="test", title="Seed Paper", abstract="")
        result = asyncio.run(explorer.explore([seed], max_depth=1, breadth=5, direction="both"))

        # Same paper from both directions should be deduped
        assert result.total_discovered == 1

    def test_05_depth_limit_respected(self):
        from backend.pipeline.literature.citation_explorer import CitationExplorer
        from backend.pipeline.literature.models import Paper

        mock_s2 = MagicMock()
        level1 = Paper(id="l1", source="s2", title="Level 1", abstract="")
        level2 = Paper(id="l2", source="s2", title="Level 2", abstract="")
        mock_s2.get_citations = AsyncMock(return_value=[level1])

        explorer = CitationExplorer(s2_source=mock_s2, openalex_source=None, cooldown=0)
        seed = Paper(id="seed1", source="test", title="Seed", abstract="")

        # max_depth=1 should only go one level
        result = asyncio.run(explorer.explore([seed], max_depth=1, breadth=5, direction="forward"))
        assert result.total_discovered == 1  # Only level1, not level2


# ─── TASK-02: TreeExplorationResult ──────────────────────────

class TestTreeExplorationResult:

    def test_06_extract_papers(self):
        from backend.pipeline.literature.citation_explorer import (
            CitationExplorer,
            TreeExplorationResult,
            TreeNode,
        )
        from backend.pipeline.literature.models import Paper

        p1 = Paper(id="p1", source="s2", title="Paper 1", abstract="")
        p2 = Paper(id="p2", source="s2", title="Paper 2", abstract="")
        result = TreeExplorationResult(
            seed_papers=1,
            tree=[
                TreeNode(paper=p1, depth=1, direction="forward"),
                TreeNode(paper=p2, depth=1, direction="backward"),
            ],
        )
        explorer = CitationExplorer()
        papers = explorer.extract_papers(result)
        assert len(papers) == 2
        assert papers[0].title == "Paper 1"

    def test_07_tree_node_fields(self):
        from backend.pipeline.literature.citation_explorer import TreeNode
        from backend.pipeline.literature.models import Paper

        p = Paper(id="t", source="test", title="Test", abstract="")
        node = TreeNode(paper=p, depth=2, direction="backward", parent_title="Parent")
        assert node.depth == 2
        assert node.direction == "backward"
        assert node.parent_title == "Parent"

    def test_08_empty_result(self):
        from backend.pipeline.literature.citation_explorer import TreeExplorationResult
        result = TreeExplorationResult()
        assert result.seed_papers == 0
        assert result.total_discovered == 0
        assert result.tree == []

    def test_09_elapsed_seconds_recorded(self):
        from backend.pipeline.literature.citation_explorer import CitationExplorer
        from backend.pipeline.literature.models import Paper

        explorer = CitationExplorer(s2_source=None, openalex_source=None)
        seed = Paper(id="s", source="t", title="S", abstract="")
        result = asyncio.run(explorer.explore([seed], max_depth=1))
        assert result.elapsed_seconds >= 0


# ─── TASK-03: Strategy Preset Wiring ────────────────────────

class TestCitationExplorePresets:

    def test_10_deep_research_has_citation_explore(self):
        from backend.pipeline.strategies.models import PipelineStrategy
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get(PipelineStrategy.DEEP_RESEARCH)
        ls_config = config.stages.get("literature_search")
        assert ls_config is not None
        assert ls_config.params.get("citation_explore") is True

    def test_11_academic_proposal_has_citation_explore(self):
        from backend.pipeline.strategies.models import PipelineStrategy
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get(PipelineStrategy.ACADEMIC_PROPOSAL)
        ls_config = config.stages.get("literature_search")
        assert ls_config is not None
        assert ls_config.params.get("citation_explore") is True

    def test_12_fast_scan_no_citation_explore(self):
        from backend.pipeline.strategies.models import PipelineStrategy
        from backend.pipeline.strategies.presets import register_presets
        from backend.pipeline.strategies.registry import StrategyRegistry

        registry = StrategyRegistry()
        register_presets(registry)
        config = registry.get(PipelineStrategy.FAST_SCAN)
        ls_config = config.stages.get("literature_search")
        # fast_scan should NOT have citation_explore
        assert ls_config is None or not ls_config.params.get("citation_explore", False)

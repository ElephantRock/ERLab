"""End-to-end mock test — runs the full pipeline with a completely mocked LLM.

Exercises: literature search → ingestion → gap analysis → idea generation →
novelty checking → feasibility scoring → proposal synthesis → export.

Uses a MockLLMProvider that returns deterministic responses for every stage.
No API keys are required. This test runs in normal CI.

Run with:  pytest -p no:asyncio backend/tests/test_pipeline/test_e2e_mock.py -v
"""

import asyncio
import logging
import shutil
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Mock heavy external dependencies before any imports ──────────────

_mock_chromadb = MagicMock()
# Make chromadb.PersistentClient().get_or_create_collection().query() return
# empty results so novelty checker returns the default high-novelty report.
_mock_collection = MagicMock()
_mock_collection.query.return_value = {"ids": [[]], "documents": [[]], "distances": [[]], "metadatas": [[]]}
_mock_collection.add.return_value = None
_mock_collection.count.return_value = 0
_mock_client = MagicMock()
_mock_client.get_or_create_collection.return_value = _mock_collection
_mock_chromadb.PersistentClient.return_value = _mock_client

sys.modules.setdefault("chromadb", _mock_chromadb)
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.config import Settings, get_settings
from backend.pipeline.autonomy.hooks import HookDispatcher
from backend.pipeline.export.export_service import ExportService
from backend.pipeline.feasibility.feasibility_scorer import FeasibilityScorer
from backend.pipeline.gap_analysis.gap_analyzer import GapAnalyzer
from backend.pipeline.generation.agent_orchestrator import AgentOrchestrator
from backend.pipeline.ingestion.chunker import DocumentChunk
from backend.pipeline.knowledge.bm25_index import BM25Index
from backend.pipeline.knowledge.embedding_service import EmbeddingService
from backend.pipeline.knowledge.vector_store import VectorStore
from backend.pipeline.literature.models import Author, Paper
from backend.pipeline.novelty.novelty_checker import NoveltyChecker
from backend.pipeline.result import PipelineResult
from backend.pipeline.stages import (
    ExportStage,
    FeasibilityScoringStage,
    GapAnalysisStage,
    IdeaGenerationStage,
    IngestionStage,
    LiteratureSearchStage,
    NoveltyCheckingStage,
    PipelineStage,
    ProposalSynthesisStage,
    StageContext,
)
from backend.pipeline.synthesis.proposal_synthesizer import ProposalSynthesizer
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)


# ── Mock LLM Provider ────────────────────────────────────────────────


class MockLLMProvider(LLMProvider):
    """Returns deterministic responses for every pipeline stage.

    Inspects the messages/schema passed to structured_output to detect
    which stage is calling and returns appropriate mock data.
    """

    def __init__(self):
        self._call_log: list[dict] = []

    async def complete(self, messages, temperature=0.7, max_tokens=4096) -> str:
        """Used by AgentOrchestrator for idea generation."""
        self._call_log.append({"method": "complete", "messages": messages})
        return (
            "Based on the analysis, here are research ideas:\n\n"
            "1. Cross-Domain Transfer via Retrieval-Augmented Generation\n"
            "   Problem: Current NLP models struggle with domain adaptation.\n"
            "   Method: We propose combining dense retrieval with domain-adversarial training.\n"
            "   Contributions: Improved cross-domain performance with minimal fine-tuning.\n"
            "   Novelty: First combination of RAG with domain-adversarial approaches.\n"
            "   Evaluation: Benchmark on 5 domains with standard metrics.\n\n"
            "2. Efficient Transformer Pruning for Edge Deployment\n"
            "   Problem: Large language models are too expensive for edge devices.\n"
            "   Method: Structured pruning guided by attention head importance scores.\n"
            "   Contributions: 50% parameter reduction with <2% accuracy loss.\n"
            "   Novelty: Novel importance metric combining gradient and attention signals.\n"
            "   Evaluation: Evaluate on GLUE and SuperGLUE benchmarks.\n"
        )

    async def complete_stream(self, messages, temperature=0.7, max_tokens=4096):
        response = await self.complete(messages, temperature, max_tokens)
        yield response

    async def structured_output(self, messages, schema, temperature=0.3) -> dict:
        """Return deterministic structured data based on the calling stage."""
        self._call_log.append({"method": "structured_output", "schema": schema})
        msg_text = " ".join(m.get("content", "") for m in messages).lower()

        # Detect stage by inspecting BOTH the system prompt and the
        # requested schema. The schema is the most reliable signal since
        # many stages mention overlapping keywords in their prompts.
        schema_props = set(schema.get("properties", {}).keys())

        # IdeatorAgent: schema has {ideas: [{title, problem_statement, ...}]}
        if "ideas" in schema_props and "title" in str(schema):
            return self._idea_response()
        # GapAnalyzer: schema has {gaps: [{title, description, gap_type, ...}]}
        elif "gaps" in schema_props:
            return self._gap_response()
        # NoveltyChecker: schema has method_novelty, problem_novelty, etc.
        elif "method_novelty" in schema_props or "novelty_arguments" in schema_props:
            return self._novelty_response()
        # FeasibilityScorer: schema has data_availability, key_risks, etc.
        elif "data_availability" in schema_props or "key_risks" in schema_props:
            return self._feasibility_response()
        # ProposalSynthesizer: schema has abstract, introduction, proposed_method
        elif "abstract" in schema_props and "proposed_method" in schema_props:
            return self._proposal_response()
        # Fallback: generate conformant output from schema
        else:
            return self._generate_from_schema(schema)

    async def embed(self, texts) -> list[list[float]]:
        return [[0.1] * 64 for _ in texts]

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-model"

    # ── Stage-Specific Responses ──────────────────────────────

    def _idea_response(self) -> dict:
        return {
            "ideas": [
                {
                    "title": "Cross-Domain Transfer via Retrieval-Augmented Generation",
                    "problem_statement": (
                        "Current NLP models struggle to transfer knowledge across domains. "
                        "Fine-tuning on a new domain requires significant labeled data, "
                        "limiting practical applicability in specialized fields."
                    ),
                    "proposed_method": (
                        "We propose combining dense retrieval with domain-adversarial "
                        "training. A gradient reversal layer encourages domain-invariant "
                        "representations while cross-attention fusion dynamically weights "
                        "retrieved passage relevance during decoding."
                    ),
                    "expected_contributions": (
                        "Improved cross-domain performance with 60% less labeled data. "
                        "A novel fusion mechanism for multi-domain retrieved contexts."
                    ),
                    "novelty_rationale": (
                        "First combination of retrieval-augmented generation with "
                        "domain-adversarial training for cross-domain NLP."
                    ),
                    "evaluation_approach": (
                        "Evaluate on MNLI, SQuAD, SciTail, Amazon Reviews, and BioASQ "
                        "with BERT, RoBERTa, and standard RAG as baselines."
                    ),
                },
                {
                    "title": "Efficient Transformer Pruning for Edge Deployment",
                    "problem_statement": (
                        "Large language models are too expensive for edge devices. "
                        "Current pruning methods lose too much accuracy at high "
                        "compression ratios."
                    ),
                    "proposed_method": (
                        "Structured pruning guided by attention head importance scores "
                        "computed from gradient and attention signal combinations. "
                        "The importance metric guides iterative head removal with "
                        "minimal accuracy degradation."
                    ),
                    "expected_contributions": (
                        "50% parameter reduction with less than 2% accuracy loss. "
                        "A novel importance metric combining gradient and attention signals."
                    ),
                    "novelty_rationale": (
                        "Novel importance metric that combines gradient information with "
                        "attention patterns for more accurate pruning decisions."
                    ),
                    "evaluation_approach": (
                        "Evaluate on GLUE and SuperGLUE benchmarks with ablation "
                        "studies on the importance metric components."
                    ),
                },
            ]
        }

    def _gap_response(self) -> dict:
        return {
            "gaps": [
                {
                    "title": "Lack of Cross-Domain Transfer in Transformer Models",
                    "description": (
                        "Current transformer-based NLP models struggle to transfer knowledge "
                        "across domains. Fine-tuning on a new domain requires significant "
                        "labeled data, limiting practical applicability."
                    ),
                    "gap_type": "methodological",
                    "related_clusters": [0, 1],
                    "potential_impact": (
                        "Enabling robust cross-domain transfer would democratize NLP "
                        "applications across specialized fields like medicine and law."
                    ),
                    "confidence": 0.85,
                },
                {
                    "title": "Scalability Bottlenecks in Retrieval-Augmented Generation",
                    "description": (
                        "RAG systems face scalability challenges when the knowledge base "
                        "exceeds millions of passages. Retrieval latency and memory "
                        "consumption become prohibitive."
                    ),
                    "gap_type": "empirical",
                    "related_clusters": [0],
                    "potential_impact": (
                        "Efficient RAG at scale would enable real-time knowledge-intensive "
                        "applications with much larger knowledge bases."
                    ),
                    "confidence": 0.75,
                },
            ]
        }

    def _novelty_response(self) -> dict:
        return {
            "method_novelty": 0.8,
            "problem_novelty": 0.7,
            "domain_transfer": 0.6,
            "combination_novelty": 0.75,
            "overall_score": 0.73,
            "novelty_arguments": (
                "The proposed approach combines retrieval-augmented generation with "
                "domain-adversarial training, which has not been previously explored. "
                "The problem formulation is moderately novel."
            ),
            "closest_match_title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
            "closest_match_similarity": 0.4,
        }

    def _feasibility_response(self) -> dict:
        return {
            "data_availability": 8.0,
            "computational_requirements": 7.0,
            "methodological_complexity": 6.5,
            "evaluation_plan": 8.0,
            "novelty_grounding": 7.0,
            "impact_potential": 8.5,
            "overall_score": 7.5,
            "reasoning": (
                "The approach is highly feasible. Required datasets (MNLI, SQuAD) are "
                "publicly available. Compute needs are moderate (1-2 GPUs for 1-2 weeks). "
                "Method implementation is straightforward based on existing frameworks."
            ),
            "estimated_timeline": "3-6 months",
            "key_risks": [
                "Data quality may vary across domains",
                "Compute budget constraints for large-scale experiments",
            ],
        }

    def _proposal_response(self) -> dict:
        return {
            "title": "Cross-Domain Retrieval-Augmented Generation with Adversarial Training",
            "abstract": (
                "This paper proposes a novel framework that combines retrieval-augmented "
                "generation (RAG) with domain-adversarial training for effective cross-domain "
                "natural language processing. Our approach leverages a domain classifier with "
                "gradient reversal to learn domain-invariant representations, while maintaining "
                "task-specific performance through targeted fine-tuning on retrieved passages. "
                "We evaluate our method across five diverse NLP benchmarks, demonstrating "
                "significant improvements in cross-domain transfer while maintaining strong "
                "in-domain performance. Our results show that the proposed framework reduces "
                "the need for domain-specific labeled data by up to 60% while achieving "
                "competitive or superior results compared to fully supervised baselines."
            ),
            "introduction": (
                "Recent advances in natural language processing have produced models with "
                "remarkable capabilities across a wide range of tasks. However, deploying "
                "these models in specialized domains such as healthcare, legal analysis, and "
                "scientific research remains challenging due to the domain gap between general "
                "pre-training data and specialized application contexts. Fine-tuning on "
                "domain-specific data is expensive and often impractical when labeled data is "
                "scarce. Retrieval-augmented generation offers a promising direction by "
                "grounding model outputs in retrieved evidence, but current approaches do not "
                "explicitly address the domain shift problem. In this work, we propose a "
                "novel framework that bridges this gap by combining RAG with domain-adversarial "
                "training, enabling effective knowledge transfer across domains without "
                "requiring extensive domain-specific supervision."
            ),
            "related_work": (
                "Our work builds on three lines of research: (1) Retrieval-augmented generation "
                "pioneered by Lewis et al., which grounds language model outputs in retrieved "
                "documents; (2) Domain adaptation techniques including adversarial training "
                "with gradient reversal layers; and (3) Multi-task learning frameworks that "
                "share representations across related tasks. While each direction has seen "
                "significant progress, their intersection remains largely unexplored."
            ),
            "proposed_method": (
                "We propose a three-stage pipeline: (1) Dense Retrieval: Given an input query, "
                "we retrieve relevant passages from a curated multi-domain knowledge base using "
                "learned dense embeddings with contrastive training. (2) Domain-Adversarial "
                "Encoding: The retrieved passages are encoded using a transformer with a gradient "
                "reversal layer that encourages domain-invariant features. The domain classifier "
                "is trained to predict the source domain, while the main encoder is trained to "
                "confuse it. (3) Cross-Attention Fusion: The generation module uses novel "
                "cross-attention layers that dynamically weight retrieved passage tokens during "
                "decoding, allowing the model to selectively attend to the most relevant "
                "evidence from any domain."
            ),
            "expected_contributions": (
                "Our contributions are: (1) A novel cross-domain RAG framework that integrates "
                "domain-adversarial training; (2) An efficient fusion mechanism for multi-domain "
                "retrieved contexts; (3) Comprehensive evaluation across 5 diverse benchmarks "
                "demonstrating 15-25% improvement in cross-domain transfer."
            ),
            "evaluation_plan": {
                "datasets": ["MNLI", "SQuAD", "SciTail", "Amazon Reviews", "BioASQ"],
                "baselines": ["BERT", "RoBERTa", "DAPT", "TAPT", "Standard RAG"],
                "metrics": ["Accuracy", "F1", "EM", "Domain Transfer Score", "Cross-Domain BLEU"],
                "ablation_design": (
                    "Remove each component independently: retrieval module, adversarial "
                    "training, and cross-attention fusion to measure individual contributions."
                ),
                "summary": (
                    "Comprehensive evaluation across 5 benchmarks with 5 baselines, "
                    "including ablation studies and domain transfer analysis."
                ),
            },
            "timeline": "6 months",
            "references": [
                {
                    "authors": "Lewis, P. et al.",
                    "year": 2020,
                    "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
                    "venue": "NeurIPS",
                    "doi": "",
                    "url": "",
                },
                {
                    "authors": "Ganin, Y. et al.",
                    "year": 2016,
                    "title": "Domain-Adversarial Training of Neural Networks",
                    "venue": "JMLR",
                    "doi": "",
                    "url": "",
                },
            ],
            "risk_mitigation": (
                "We mitigate risks through: (1) Starting with well-established benchmarks; "
                "(2) Using pre-trained retrieval models as initialization; "
                "(3) Fallback to simpler fusion mechanisms if cross-attention proves unstable."
            ),
        }

    def _generate_from_schema(self, schema: dict) -> dict:
        """Fallback: generate conformant output from a JSON schema."""
        result = {}
        props = schema.get("properties", {})
        for key, prop_schema in props.items():
            prop_type = prop_schema.get("type")
            if prop_type == "string":
                result[key] = f"Generated {key}"
            elif prop_type == "number":
                result[key] = 0.7
            elif prop_type == "integer":
                result[key] = 1
            elif prop_type == "array":
                items = prop_schema.get("items", {})
                if items.get("type") == "object":
                    result[key] = [self._generate_from_schema(items)]
                elif items.get("type") == "string":
                    result[key] = [f"{key}_item"]
                elif items.get("type") == "integer":
                    result[key] = [1]
                else:
                    result[key] = []
            elif prop_type == "object":
                result[key] = self._generate_from_schema(prop_schema)
        return result


# ── Fake Embedding Provider ──────────────────────────────────────────


class FakeEmbeddingProvider:
    """Returns deterministic fake vectors — no external API needed."""

    def __init__(self, dimension: int = 64):
        self._dim = dimension

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self._dim for _ in texts]

    @property
    def dimension(self) -> int:
        return self._dim

    @property
    def provider_name(self) -> str:
        return "fake-mock"


# ── Fixtures ─────────────────────────────────────────────────────────


def _make_settings(tmp_dir: Path) -> Settings:
    """Create minimal settings with all optional features disabled."""
    base = get_settings()
    return Settings(
        default_provider="ollama",
        anthropic_api_key="",
        anthropic_model="mock-model",
        anthropic_base_url="http://localhost:11434",
        openai_api_key="",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        chroma_persist_dir=str(tmp_dir / "chroma"),
        bm25_persist_dir=str(tmp_dir / "bm25"),
        embedding_dimension=64,
        database_url=f"sqlite:///{tmp_dir / 'test_mock_e2e.db'}",
        s1_parser_mode="raw",
        s1_parser_url="",
        knowledge_graph_path=str(tmp_dir / "kg.json"),
        world_model_path=str(tmp_dir / "world_model.json"),
        goals_path=str(tmp_dir / "goals.json"),
        # Disable all optional subsystems
        memory_enabled=False,
        self_improve_enabled=False,
        governance_enabled=False,
        budget_enabled=False,
        autonomy_enabled=False,
        skills_enabled=False,
        multi_agent_enabled=False,
        # Disable new features
        embedding_fallback_enabled=False,
        query_transform_enabled=False,
        reranker_enabled=False,
        retrieval_quality_scoring_enabled=False,
        citation_novelty_enabled=False,
        embedding_novelty_enabled=False,
        faithfulness_check_enabled=False,
        contradiction_detection_enabled=False,
        reasoning_verification_enabled=False,
        dynamic_agents_enabled=False,
        sub_goal_generation_enabled=False,
        evaluation_framework_enabled=False,
        sandboxing_enabled=False,
        observability_enabled=False,
        metacognitive_enabled=False,
        mcp_enabled=False,
        context_management_enabled=False,
        streaming_enabled=False,
        consolidation_enabled=False,
        adaptation_enabled=False,
        graph_rag_enabled=False,
        tool_discovery_enabled=False,
        negotiation_enabled=False,
        session_enabled=False,
        counterfactual_enabled=False,
        quality_backloop_enabled=False,
        cross_stage_context_enabled=False,
        plugin_verification_enabled=False,
        dependency_tracking_enabled=False,
        reactive_streams_enabled=False,
        activation_enabled=False,
        versioning_enabled=False,
        tree_of_thought_enabled=False,
        litellm_fallback_enabled=False,
        caching_enabled=False,
        resilience_enabled=False,
        model_routing_enabled=False,
        cost_routing_enabled=False,
        heartbeat_enabled=False,
        compaction_enabled=False,
        autonomy_schedule_enabled=False,
    )


def _make_mock_papers() -> list[Paper]:
    """Create deterministic mock papers for the literature search stage."""
    return [
        Paper(
            id=f"mock_p{i}",
            source="test",
            title=f"Advances in NLP: Transformer Architectures and Applications {i}",
            abstract=(
                f"This paper investigates novel approaches to natural language processing "
                f"using transformer-based architectures. We propose a method that combines "
                f"multi-head attention with retrieval-augmented generation for improved "
                f"performance on knowledge-intensive tasks. Our experiments demonstrate "
                f"significant improvements over existing baselines on standard benchmarks."
            ),
            authors=[Author(name=f"Author {i}")],
            year=2024,
            venue="ACL",
            citation_count=10 + i,
            url=f"https://example.com/paper/{i}",
        )
        for i in range(5)
    ]


@pytest.fixture(scope="module")
def test_env():
    """Create isolated test directories, cleaned up after module."""
    tmp = Path("./data/test_mock_e2e")
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "chroma").mkdir(exist_ok=True)
    (tmp / "bm25").mkdir(exist_ok=True)
    (tmp / "exports").mkdir(exist_ok=True)
    settings = _make_settings(tmp)
    yield tmp, settings
    shutil.rmtree(tmp, ignore_errors=True)


class TestEndToEndMock:
    """Full pipeline test with completely mocked LLM — no API keys needed.

    Runs through all 8 stages with deterministic mock data, verifying
    that the pipeline orchestration logic correctly passes data between
    stages and produces valid output at each step.
    """

    def test_full_pipeline_all_stages(self, test_env):
        """Execute stages 1-8 in order with mock data and verify each stage."""
        tmp, settings = test_env

        # ── Shared services ──────────────────────────────────

        mock_provider = MockLLMProvider()
        fake_embedding = FakeEmbeddingProvider(64)
        embedding_service = EmbeddingService(fake_embedding, batch_size=10)
        hooks = HookDispatcher()
        mock_papers = _make_mock_papers()

        # Patch get_settings for stages that call it internally
        with patch("backend.config.get_settings", return_value=settings):
            result = PipelineResult()
            result.run_id = "test_mock_run"

            ctx = StageContext(
                result=result,
                domain="AI/NLP",
                run_id="test_mock_run",
                db_run_id=None,
                params={},
                search_queries=[
                    "natural language processing recent advances",
                    "NLP transformer models open problems",
                ],
                max_gaps=2,
                rounds=1,
                ideas_per=2,
                export_format="markdown",
            )

            # ── Stage 1: Literature Search ────────────────────
            # Use a mock search service that returns our fake papers
            mock_search = MagicMock()
            mock_search.search_all = AsyncMock(return_value=mock_papers)

            stage1 = LiteratureSearchStage(mock_search, hooks)
            should_continue = asyncio.run(stage1.execute(ctx))
            assert should_continue is True, "Stage 1: Pipeline should continue"
            # 2 queries × 5 papers each = 10 total (mock returns same list per query)
            assert ctx.result.papers_found >= len(mock_papers), (
                f"Stage 1: Expected at least {len(mock_papers)} papers, got {ctx.result.papers_found}"
            )
            assert len(ctx.all_papers) >= len(mock_papers)
            logger.info(
                "Stage 1 (literature_search): %d papers found", ctx.result.papers_found
            )

            # ── Stage 2: Ingestion ────────────────────────────
            mock_store = MagicMock(spec=VectorStore)
            mock_store.add_papers = AsyncMock(return_value=len(mock_papers))
            mock_bm25 = MagicMock(spec=BM25Index)
            mock_bm25.add_documents = MagicMock(return_value=None)

            stage2 = IngestionStage(mock_store, mock_bm25, embedding_service)
            should_continue = asyncio.run(stage2.execute(ctx))
            assert should_continue is True
            mock_store.add_papers.assert_called_once()
            logger.info("Stage 2 (ingestion): completed")

            # ── Stage 3: Gap Analysis ─────────────────────────
            gap_analyzer = GapAnalyzer(mock_provider)
            mock_goal_manager = MagicMock()
            mock_goal_manager.create_from_gaps.return_value = []

            stage3 = GapAnalysisStage(
                gap_analyzer, mock_goal_manager, hooks, memory=None
            )
            should_continue = asyncio.run(stage3.execute(ctx))
            assert should_continue is True
            assert len(ctx.result.gaps) >= 1, "Stage 3: No research gaps identified"
            for gap in ctx.result.gaps:
                assert gap.title, "Gap must have a title"
                assert gap.description, "Gap must have a description"
            logger.info("Stage 3 (gap_analysis): %d gaps", len(ctx.result.gaps))

            # ── Stage 4: Idea Generation ──────────────────────
            agent = AgentOrchestrator(mock_provider)

            stage4 = IdeaGenerationStage(
                agent, hooks, dag_executor=None, dag_agents=None, provider=mock_provider
            )
            should_continue = asyncio.run(stage4.execute(ctx))
            assert should_continue is True
            assert len(ctx.result.ideas) >= 1, "Stage 4: No ideas generated"
            for idea in ctx.result.ideas:
                assert idea.title, "Idea must have a title"
                assert idea.proposed_method, "Idea must have a proposed method"
            logger.info("Stage 4 (idea_generation): %d ideas", len(ctx.result.ideas))

            # ── Stage 5: Novelty Checking ─────────────────────
            # Use a mock vector store that returns empty results,
            # so NoveltyChecker returns the default high-novelty report.
            mock_store_empty = MagicMock(spec=VectorStore)
            mock_store_empty.query = AsyncMock(return_value=[])

            novelty_checker = NoveltyChecker(mock_provider, mock_store_empty)
            stage5 = NoveltyCheckingStage(novelty_checker, hooks)
            should_continue = asyncio.run(stage5.execute(ctx))
            assert should_continue is True
            assert len(ctx.result.novelty_reports) >= 1, "Stage 5: No novelty reports"
            for idx, report in ctx.result.novelty_reports.items():
                assert report.overall_score is not None
                assert 0 <= report.overall_score <= 1, (
                    f"Novelty score {report.overall_score} not in [0, 1]"
                )
            logger.info(
                "Stage 5 (novelty_checking): %d reports", len(ctx.result.novelty_reports)
            )

            # ── Stage 6: Feasibility Scoring ──────────────────
            feasibility_scorer = FeasibilityScorer(mock_provider)
            stage6 = FeasibilityScoringStage(feasibility_scorer)
            should_continue = asyncio.run(stage6.execute(ctx))
            assert should_continue is True
            assert len(ctx.result.feasibility_reports) >= 1, "Stage 6: No feasibility reports"
            for idx, report in ctx.result.feasibility_reports.items():
                assert report.overall_score is not None
                assert 0 <= report.overall_score <= 10, (
                    f"Feasibility score {report.overall_score} not in [0, 10]"
                )
            logger.info(
                "Stage 6 (feasibility_scoring): %d reports",
                len(ctx.result.feasibility_reports),
            )

            # ── Stage 7: Proposal Synthesis ───────────────────
            synthesizer = ProposalSynthesizer(mock_provider)
            stage7 = ProposalSynthesisStage(synthesizer)
            should_continue = asyncio.run(stage7.execute(ctx))
            assert should_continue is True
            assert len(ctx.result.proposals) >= 1, "Stage 7: No proposals generated"
            for idx, proposal in ctx.result.proposals.items():
                md = proposal.to_markdown()
                assert md, "Proposal must generate markdown"
                assert len(md) > 50, "Proposal markdown is too short"
            logger.info(
                "Stage 7 (proposal_synthesis): %d proposals", len(ctx.result.proposals)
            )

            # ── Stage 8: Export ────────────────────────────────
            export_service = ExportService(output_dir=str(tmp / "exports"))
            stage8 = ExportStage(export_service)
            should_continue = asyncio.run(stage8.execute(ctx))
            assert should_continue is True
            assert len(ctx.result.export_paths) >= 1, "Stage 8: No files exported"
            for idx, path in ctx.result.export_paths.items():
                assert Path(path).exists(), f"Export file missing: {path}"
                content = Path(path).read_text(encoding="utf-8")
                assert len(content) > 50, f"Export file too short: {path}"
            logger.info("Stage 8 (export): %d files", len(ctx.result.export_paths))

            # ── Verify End-to-End Data Flow ───────────────────
            assert ctx.result.run_id == "test_mock_run"
            assert ctx.result.papers_found > 0
            assert len(ctx.result.gaps) >= 1
            assert len(ctx.result.ideas) >= 1
            assert len(ctx.result.novelty_reports) >= 1
            assert len(ctx.result.feasibility_reports) >= 1
            assert len(ctx.result.proposals) >= 1
            assert len(ctx.result.export_paths) >= 1

            logger.info(
                "=== Mock E2E Complete: run=%s papers=%d gaps=%d ideas=%d "
                "novelty=%d feasibility=%d proposals=%d exports=%d ===",
                ctx.result.run_id,
                ctx.result.papers_found,
                len(ctx.result.gaps),
                len(ctx.result.ideas),
                len(ctx.result.novelty_reports),
                len(ctx.result.feasibility_reports),
                len(ctx.result.proposals),
                len(ctx.result.export_paths),
            )

    def test_mock_provider_returns_deterministic(self):
        """Verify MockLLMProvider returns consistent results across calls."""
        provider = MockLLMProvider()

        # Gap analysis calls should return identical results
        gap_schema = {
            "type": "object",
            "properties": {
                "gaps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "gap_type": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                    },
                }
            },
        }
        msg_gap = [{"role": "user", "content": "Identify research gaps in the clusters"}]

        r1 = asyncio.run(provider.structured_output(msg_gap, gap_schema))
        r2 = asyncio.run(provider.structured_output(msg_gap, gap_schema))
        assert r1 == r2, "Gap responses should be deterministic"

        # Feasibility calls should return identical results
        msg_feas = [{"role": "user", "content": "You are a research feasibility evaluator"}]
        f1 = asyncio.run(provider.structured_output(msg_feas, {}))
        f2 = asyncio.run(provider.structured_output(msg_feas, {}))
        assert f1 == f2, "Feasibility responses should be deterministic"

    def test_mock_provider_handles_all_stages(self):
        """Verify MockLLMProvider returns correct data for each pipeline stage schema."""
        provider = MockLLMProvider()

        # Idea generation (IdeatorAgent schema)
        idea_schema = {
            "type": "object",
            "properties": {
                "ideas": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "problem_statement": {"type": "string"},
                            "proposed_method": {"type": "string"},
                        },
                    },
                }
            },
        }
        result = asyncio.run(provider.structured_output([], idea_schema))
        assert "ideas" in result
        assert len(result["ideas"]) == 2
        assert result["ideas"][0]["title"]

        # Gap analysis (GapAnalyzer schema)
        gap_schema = {
            "type": "object",
            "properties": {
                "gaps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "gap_type": {"type": "string"},
                            "confidence": {"type": "number"},
                        },
                    },
                }
            },
        }
        result = asyncio.run(provider.structured_output([], gap_schema))
        assert "gaps" in result
        assert len(result["gaps"]) == 2

        # Novelty (NoveltyChecker schema)
        novelty_schema = {
            "type": "object",
            "properties": {
                "method_novelty": {"type": "number"},
                "problem_novelty": {"type": "number"},
                "novelty_arguments": {"type": "string"},
                "overall_score": {"type": "number"},
            },
        }
        result = asyncio.run(provider.structured_output([], novelty_schema))
        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 1

        # Feasibility (FeasibilityScorer schema)
        feas_schema = {
            "type": "object",
            "properties": {
                "data_availability": {"type": "number"},
                "key_risks": {"type": "array", "items": {"type": "string"}},
                "overall_score": {"type": "number"},
                "reasoning": {"type": "string"},
            },
        }
        result = asyncio.run(provider.structured_output([], feas_schema))
        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 10

        # Proposal (ProposalSynthesizer schema)
        proposal_schema = {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "abstract": {"type": "string"},
                "proposed_method": {"type": "string"},
                "introduction": {"type": "string"},
            },
        }
        result = asyncio.run(provider.structured_output([], proposal_schema))
        assert "title" in result
        assert "abstract" in result
        assert "proposed_method" in result

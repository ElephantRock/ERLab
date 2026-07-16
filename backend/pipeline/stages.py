"""Pipeline stages — composable units following the ActivationPipeline pattern."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.ingestion.chunker import DocumentChunk  # noqa: F401 — re-exported by stages
from backend.pipeline.novelty.novelty_checker import NoveltyReport  # noqa: F401 — legacy compat in NoveltyCheckingStage
from backend.pipeline.synthesis.proposal_synthesizer import ResearchProposal  # noqa: F401 — used by ProposalSynthesisStage
from backend.pipeline.verification.citation_claim_auditor import (  # noqa: F401 — used by CitationAuditStage
    CitationAuditReport,
    CitationClaimAuditor,
    create_skipped_report,
)

if TYPE_CHECKING:
    from backend.providers.base import LLMProvider
    from backend.pipeline.result import PipelineResult

logger = logging.getLogger(__name__)


@dataclass
class StageContext:
    """Shared mutable state passed between stages."""

    result: PipelineResult
    all_papers: list = field(default_factory=list)
    db_run_id: int | None = None
    params: dict = field(default_factory=dict)
    domain: str = "AI/NLP"
    run_id: str = ""
    search_queries: list[str] | None = None
    max_gaps: int = 5
    rounds: int = 2
    ideas_per: int = 3
    export_format: str | None = "markdown"
    provider_override: Any = None  # LLMProvider override for model routing
    journal: Any = None  # B162: Optional JournalWriter or callback
    receipts: list = field(default_factory=list)  # ModelReceipts collected during this stage
    # P0.1: Corpus provenance — populated by LiteratureSearchStage
    search_query_data: list = field(default_factory=list)  # list[SearchQueryData]
    candidate_papers: list = field(default_factory=list)  # list[CandidateWithDiscoveries]
    # P0.2.5: Execution linkage expectations for governed persistence
    execution_linkage_expectations: list = field(default_factory=list)
    # P0.2.7: Explicit governed-search marker (replaces context-truthiness)
    governed_search_context: Any = None  # GovernedSearchContext | None


# Stages that do NOT use LLM models — no receipt required.
# All other stages are model-backed and should produce receipts.
NON_MODEL_STAGES: frozenset[str] = frozenset({
    "literature_search",
    "mechanical_metrics",
    "export",
})


class PipelineStage(ABC):
    """Base class for pipeline stages."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def execute(self, ctx: StageContext) -> bool:
        """Execute the stage. Return False to halt the pipeline."""
        ...


class LiteratureSearchStage(PipelineStage):
    def __init__(self, search, hooks, gateway=None, persistence=None):
        self._search = search
        self._hooks = hooks
        self._gateway = gateway
        self._persistence = persistence

    @property
    def name(self) -> str:
        return "literature_search"

    async def execute(self, ctx: StageContext) -> bool:
        # Pre-run knowledge library query (B158)
        pre_existing = []
        try:
            from backend.pipeline.knowledge.integration import KnowledgeIntegrationService
            service = KnowledgeIntegrationService()
            existing = service.query_existing_knowledge(ctx.domain)
            if existing.get("has_knowledge"):
                pre_existing = service._indexer.get_existing_papers(ctx.domain, limit=50)
                logger.info(
                    "Knowledge library: %d pre-existing papers for '%s'",
                    len(pre_existing), ctx.domain,
                )
            service.close()
        except Exception as e:
            logger.debug("Knowledge library query skipped: %s", e)

        # B160: Also retrieve locally uploaded documents from vector store
        local_docs = []
        try:
            from backend.config import get_settings
            from backend.pipeline.knowledge.embedding_service import EmbeddingService
            from backend.pipeline.knowledge.embedding_providers import create_embedding_provider
            from backend.pipeline.knowledge.vector_store import VectorStore

            settings = get_settings()
            if settings.embedding_base_url:
                _emb_base = settings.embedding_base_url.rstrip('/')
                if not _emb_base.endswith('/v1'):
                    _emb_base += '/v1'
            elif settings.embedding_provider == "lmstudio":
                _emb_base = settings.lmstudio_base_url.rstrip('/') + '/v1'
            else:
                _emb_base = settings.ollama_base_url
            embedding_provider = create_embedding_provider(
                provider_name=settings.embedding_provider,
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
                base_url=_emb_base,
                dimension=settings.embedding_dimension or None,
            )
            embedding = EmbeddingService(embedding_provider, batch_size=settings.embedding_batch_size)
            store = VectorStore(settings.chroma_persist_dir, embedding)

            # Query vector store for any documents matching the domain
            results = await store.query(ctx.domain, n_results=20)
            for r in results:
                meta = r.get("metadata", {})
                if meta.get("source") == "local_upload":
                    local_docs.append(r)
            if local_docs:
                logger.info("Found %d locally uploaded documents for '%s'", len(local_docs), ctx.domain)
        except Exception as e:
            logger.debug("Local document retrieval skipped: %s", e)

        queries = ctx.search_queries or [
            f"{ctx.domain} recent advances",
            f"{ctx.domain} open problems",
        ]

        # LLM query expansion: generate additional search queries
        query_gen_log = {
            "query_generation_attempted": False,
            "generated_query_count": 0,
            "accepted_query_count": 0,
            "rejected_query_count": 0,
            "enforcement_applied": False,
            "routed_model": "",
            "actual_model": "",
            "degraded": False,
        }
        if self._gateway is not None:
            try:
                from backend.pipeline.gateway.llm_repair_and_query import LLMQueryGenerator

                query_gen_log["query_generation_attempted"] = True
                gen = LLMQueryGenerator(self._gateway)
                expanded = await gen.generate_queries(
                    domain=str(ctx.domain),
                    topic=str(ctx.domain),
                    n_queries=3,
                    run_id=ctx.run_id or "",
                )
                query_gen_log["generated_query_count"] = len(expanded)

                # Filter and deduplicate
                original_lower = {q.lower().strip() for q in queries}
                for eq in expanded:
                    eq_stripped = eq.strip()
                    if not eq_stripped or len(eq_stripped) < 5:
                        query_gen_log["rejected_query_count"] += 1
                        continue
                    if len(eq_stripped) > 200:
                        query_gen_log["rejected_query_count"] += 1
                        continue
                    if eq_stripped.lower() in original_lower:
                        query_gen_log["rejected_query_count"] += 1
                        continue
                    queries.append(eq_stripped)
                    original_lower.add(eq_stripped.lower())
                    query_gen_log["accepted_query_count"] += 1

                # Capture enforcement fields
                call_log = self._gateway.get_call_log(limit=5)
                qg_calls = [c for c in call_log if c.get("stage") == "query_generation"]
                if qg_calls:
                    last = qg_calls[-1]
                    query_gen_log["enforcement_applied"] = last.get("enforcement_applied", False)
                    query_gen_log["routed_model"] = last.get("routed_model", "")
                    query_gen_log["actual_model"] = last.get("model", "")
                    query_gen_log["degraded"] = last.get("degraded", False)

                logger.info(
                    "LLM query expansion: %d generated, %d accepted, %d rejected (enforced=%s)",
                    query_gen_log["generated_query_count"],
                    query_gen_log["accepted_query_count"],
                    query_gen_log["rejected_query_count"],
                    query_gen_log["enforcement_applied"],
                )
            except Exception as e:
                logger.debug("LLM query expansion failed (non-fatal): %s", e)
        else:
            logger.debug("LLM query expansion skipped (no gateway available)")
        # P0.1: Build SearchQueryData with deterministic query_keys
        from backend.pipeline.persistence import (
            SearchQueryData, CandidateWithDiscoveries, DiscoveryMetadata,
            compute_query_key,
        )

        search_query_data: list[SearchQueryData] = []
        for seq, q in enumerate(queries):
            # Determine origin: first 2 are base templates, rest are LLM-generated
            if seq < 2 and not ctx.search_queries:
                q_type, q_origin = "template", "base"
            else:
                q_type, q_origin = "llm_generated", "llm"
            q_key = compute_query_key(q, q_type, q_origin, seq)
            search_query_data.append(SearchQueryData(
                query_text=q, query_type=q_type,
                generation_origin=q_origin, sequence_number=seq,
                query_key=q_key,
            ))

        # P0.2.2: Pre-resolve search_query_id before the fan-out so the
        # execution recorder can link execution rows to the correct query.
        from backend.db.database import _get_engine
        from backend.pipeline.literature.contracts import SearchBatchOutcome

        db_engine = None
        query_ids_by_key: dict[str, int] = {}
        if ctx.db_run_id:
            db_engine = _get_engine()
            # P0.2.6: Ensure pending run reconciliation ledger exists before
            # outbound source work so a crash leaves an explicit incomplete posture.
            from backend.pipeline.literature.run_reconciliation import (
                ensure_pending_reconciliation,
            )
            ensure_pending_reconciliation(db_engine, ctx.db_run_id)
            # ensure_search_queries is a non-corpus short transaction.
            query_ids_by_key = self._persistence.ensure_search_queries(
                search_query_data, ctx.db_run_id,
            )

        # Parallel query fan-out with provenance.
        # Governed path: returns SearchBatchOutcome (candidates + executions).
        # Legacy path (no db_run_id): returns list[CandidateWithDiscoveries].
        query_results = await asyncio.gather(
            *(
                self._search.search_all_with_provenance(
                    q, sqd.query_key, limit_per_source=20,
                    search_query_id=query_ids_by_key.get(sqd.query_key),
                    db_engine=db_engine,
                )
                for q, sqd in zip(queries, search_query_data, strict=True)
            ),
            return_exceptions=True,
        )

        all_candidates: list[CandidateWithDiscoveries] = []
        all_linkage_expectations: list = []
        for sqd, result in zip(search_query_data, query_results, strict=True):
            if isinstance(result, Exception):
                logger.warning("Query '%s' failed: %s", sqd.query_text[:50], result)
            elif isinstance(result, SearchBatchOutcome):
                all_candidates.extend(result.candidates)
                # P0.2.5: Collect linkage expectations for governed persistence
                for exec_outcome in result.executions:
                    from backend.pipeline.literature.contracts import ExecutionLinkageExpectation
                    if exec_outcome.status in ("success", "partial"):
                        all_linkage_expectations.append(ExecutionLinkageExpectation(
                            execution_id=exec_outcome.execution_id,
                            search_query_id=query_ids_by_key.get(sqd.query_key, 0),
                            source=exec_outcome.source,
                            expected_discovery_count=len(exec_outcome.results),
                            accounting_status="reconciled",
                        ))
                    elif exec_outcome.status == "skipped":
                        all_linkage_expectations.append(ExecutionLinkageExpectation(
                            execution_id=exec_outcome.execution_id,
                            search_query_id=query_ids_by_key.get(sqd.query_key, 0),
                            source=exec_outcome.source,
                            expected_discovery_count=None,
                            accounting_status="incomplete",
                        ))
                logger.info(
                    "Found %d papers for query: %s",
                    len(result.candidates), sqd.query_text[:50],
                )
            elif isinstance(result, list):
                all_candidates.extend(result)
                logger.info("Found %d papers for query: %s", len(result), sqd.query_text[:50])
            else:
                logger.warning(
                    "Query '%s' returned unexpected type: %s",
                    sqd.query_text[:50], type(result),
                )

        # Cross-query dedup with provenance merging
        # When the same paper appears through different queries, merge discovery lists
        from difflib import SequenceMatcher
        seen_keys: dict[str, CandidateWithDiscoveries] = {}

        for cand in all_candidates:
            p = cand.paper
            key = p.doi if getattr(p, 'doi', None) else p.title.lower().strip()
            if key in seen_keys:
                # Merge discovery events from this candidate into the existing one
                seen_keys[key].discoveries.extend(cand.discoveries)
            else:
                seen_keys[key] = cand

        unique_candidates = list(seen_keys.values())

        # G6: Fuzzy dedup — merge discovery lists for near-duplicates
        fuzzy_unique: list[CandidateWithDiscoveries] = []
        for cand in unique_candidates:
            paper_title = cand.paper.title.lower().strip()
            is_dup = any(
                SequenceMatcher(
                    None,
                    paper_title,
                    existing.paper.title.lower().strip(),
                ).ratio() > 0.85
                for existing in fuzzy_unique
            )
            if not is_dup:
                fuzzy_unique.append(cand)
            else:
                # Find the matching candidate and merge discoveries
                for existing in fuzzy_unique:
                    if SequenceMatcher(
                        None, paper_title,
                        existing.paper.title.lower().strip(),
                    ).ratio() > 0.85:
                        existing.discoveries.extend(cand.discoveries)
                        break

        if len(fuzzy_unique) < len(unique_candidates):
            logger.info(
                "Fuzzy dedup removed %d near-duplicates (%d → %d)",
                len(unique_candidates) - len(fuzzy_unique),
                len(unique_candidates), len(fuzzy_unique),
            )
        unique_candidates = fuzzy_unique

        # Extract bare papers for backward compatibility
        unique = [c.paper for c in unique_candidates]

        # Merge pre-existing knowledge library papers
        if pre_existing:
            from backend.pipeline.literature.models import Paper, Author
            for entry in pre_existing:
                try:
                    content = json.loads(entry.get("content", "{}")) if isinstance(entry.get("content"), str) else entry.get("content", {})
                    paper = Paper(
                        id=f"lib:{entry.get('id', '')}",
                        source="knowledge_library",
                        title=entry.get("title", ""),
                        abstract=content.get("abstract", ""),
                        authors=[],
                        year=content.get("year"),
                        doi=content.get("doi"),
                    )
                    key = paper.doi if paper.doi else paper.title.lower().strip()
                    if key not in seen:
                        seen.add(key)
                        unique.append(paper)
                except Exception as e:
                    logger.debug("Failed to merge library paper: %s", e)
            logger.info("Merged %d papers from knowledge library", len([p for p in unique if getattr(p, 'source', '') == 'knowledge_library']))

        # B160: Merge locally uploaded documents
        if local_docs:
            from backend.pipeline.literature.models import Paper
            for doc in local_docs:
                meta = doc.get("metadata", {})
                content = doc.get("content", "")
                doc_id = meta.get("paper_id", "")
                title = meta.get("title", doc_id)
                paper = Paper(
                    id=f"upload:{doc_id}",
                    source="local_upload",
                    title=title,
                    abstract=content[:500] if content else "",
                    authors=[],
                )
                key = paper.title.lower().strip()
                if key not in seen:
                    seen.add(key)
                    unique.append(paper)
            logger.info(
                "Merged %d locally uploaded documents",
                len([p for p in unique if getattr(p, 'source', '') == 'local_upload']),
            )

        # B161: Citation tree exploration for deep_research strategy
        try:
            explore_enabled = False
            strat_config = ctx.params.get("strategy_config") if ctx.params else None
            if strat_config:
                ls_config = strat_config.stages.get("literature_search")
                if ls_config and ls_config.params.get("citation_explore"):
                    explore_enabled = True

            if explore_enabled and unique:
                from backend.pipeline.literature.citation_explorer import CitationExplorer
                from backend.pipeline.literature.semantic_scholar import SemanticScholarSource
                from backend.pipeline.literature.openalex_source import OpenAlexSource

                s2 = None
                oa = None
                try:
                    from backend.config import get_settings
                    settings = get_settings()
                    s2 = SemanticScholarSource(api_key=settings.s2_api_key or "")
                    oa = OpenAlexSource(email=settings.openalex_email or "")
                except Exception:
                    pass

                explorer = CitationExplorer(s2_source=s2, openalex_source=oa, cooldown=1.0)
                tree_result = await explorer.explore(
                    seed_papers=unique[:10],
                    max_depth=1,
                    breadth=5,
                    direction="backward",
                )
                if tree_result.total_discovered > 0:
                    tree_papers = explorer.extract_papers(tree_result)
                    added = 0
                    for tp in tree_papers:
                        key = tp.doi if tp.doi else tp.title.lower().strip()
                        if key not in seen:
                            seen.add(key)
                            unique.append(tp)
                            added += 1
                    logger.info(
                        "Citation tree: %d foundational papers discovered, %d new added",
                        tree_result.total_discovered, added,
                    )
        except Exception as e:
            logger.debug("Citation tree exploration skipped: %s", e)

        ctx.all_papers = unique
        ctx.candidate_papers = unique_candidates
        ctx.search_query_data = search_query_data
        ctx.execution_linkage_expectations = all_linkage_expectations
        # P0.2.7: Populate explicit governed-search marker if governed path ran.
        if db_engine is not None and ctx.db_run_id:
            from backend.pipeline.literature.contracts import GovernedSearchContext
            ctx.governed_search_context = GovernedSearchContext(
                schema_version="governed_search_context_v1",
                search_query_data=tuple(search_query_data),
                candidate_papers=tuple(unique_candidates),
                execution_linkage_expectations=tuple(all_linkage_expectations),
            )
        ctx.result.papers_found = len(unique)
        logger.info("Total unique papers: %d (from %d total)", len(unique), len(all_candidates))

        # B162: Journal note
        if ctx.journal:
            try:
                ctx.journal.add_note("literature_search", f"Found {len(unique)} unique papers from {len(all_candidates)} total", {
                    "unique_papers": len(unique),
                    "total_found": len(all_candidates),
                })
            except Exception:
                pass

        if not all_candidates:
            logger.warning(
                "No papers found from any source. Halting pipeline — "
                "gap analysis requires paper abstracts as input."
            )
            return False  # should_continue=False → triggers early-exit abort
        return True


class IngestionStage(PipelineStage):
    def __init__(self, store, bm25, embedding, kg=None, provider=None, governed_runtime=None):
        self._store = store
        self._bm25 = bm25
        self._embedding = embedding
        self._kg = kg
        self._provider = provider
        self._governed_runtime = governed_runtime

    @property
    def name(self) -> str:
        return "ingestion"

    async def execute(self, ctx: StageContext) -> bool:
        # Deduplicate papers by ID — same paper can appear across multiple queries
        seen_ids = set()
        unique_papers = []
        for paper in ctx.all_papers:
            if paper.id not in seen_ids:
                seen_ids.add(paper.id)
                unique_papers.append(paper)
        ctx.all_papers = unique_papers
        logger.info("Ingestion: %d unique papers (from %d total)", len(unique_papers), len(ctx.all_papers))

        chunks = []
        for paper in ctx.all_papers:
            text = f"{paper.title}\n\n{paper.abstract or ''}"
            paper_chunks = [
                DocumentChunk(
                    text=text,
                    paper_id=paper.id,
                    section="abstract",
                    chunk_index=0,
                )
            ]
            chunks.append(paper_chunks)

        added = await self._store.add_papers(ctx.all_papers, chunks)
        logger.info("Added %d chunks to knowledge base", added)

        # P0.3.4B: Governed indexing for provenance_v1 runs.
        # Index through the governed vector indexer to create verified
        # vector_index_records that scoped retrieval can consume.
        if ctx.db_run_id:
            try:
                await self._index_governed(ctx, unique_papers)
            except Exception as e:
                logger.warning("Governed vector indexing failed (non-fatal): %s", e)

        all_ids, all_texts, all_metas = [], [], []
        for paper, paper_chunks in zip(ctx.all_papers, chunks, strict=True):
            for j, chunk in enumerate(paper_chunks):
                all_ids.append(f"{paper.id}_chunk_{j}")
                all_texts.append(chunk.text)
                all_metas.append(
                    {
                        "paper_id": paper.id,
                        "paper_title": paper.title[:500],
                        "source": paper.source,
                    }
                )
        if all_ids:
            self._bm25.add_documents(all_ids, all_texts, all_metas)
            logger.info("Synced %d documents to BM25 index", len(all_ids))

        # Write to Knowledge Graph
        if self._kg:
            from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
            from backend.pipeline.knowledge.truth import TruthValue

            for paper in ctx.all_papers:
                entity = KnowledgeEntity(
                    id=f"paper:{paper.id}",
                    entity_type=EntityType.PAPER,
                    name=paper.title,
                    properties={
                        "source": paper.source,
                        "year": paper.year,
                        "citation_count": paper.citation_count,
                    },
                    truth=TruthValue.from_observation(frequency=0.9),
                )
                self._kg.add_entity(entity)
            self._kg.save()
            logger.info("Added %d paper entities to Knowledge Graph", len(ctx.all_papers))

            # Extract relationships between papers (Fix #4)
            try:
                from backend.pipeline.knowledge.relationship_extractor import extract_relationships
                # Limit to top 10 papers for relationship extraction to avoid O(n) LLM bottleneck
                top_papers = ctx.all_papers[:10]
                rels = await extract_relationships(top_papers, ctx.provider_override or self._provider)
                for rel in rels:
                    self._kg.add_relationship(rel)
                if rels:
                    self._kg.save()
                    logger.info("Added %d paper relationships to Knowledge Graph", len(rels))
            except Exception as e:
                logger.warning("Relationship extraction failed (non-fatal): %s", e)

        return True

    async def _index_governed(self, ctx: StageContext, papers: list) -> None:
        """P0.3.4B: Index papers through the governed vector indexer.

        Creates verified vector_index_records for provenance_v1 runs.
        The legacy store.add_papers continues to run for backward compat.
        """
        if not papers or not ctx.db_run_id:
            return

        try:
            from backend.db.database import _get_engine, get_session
            from backend.pipeline.provenance_gate import (
                load_run_provenance_contract,
                select_run_execution_mode,
            )
            from backend.pipeline.vector_contracts import (
                build_title_abstract_document,
            )
            from backend.pipeline.vector_indexer import index_document
            from backend.pipeline.vector_backend import GovernedVectorBackend
            from backend.pipeline.vector_access_policy import resolve_profile_id
            from backend.config import get_settings
            from sqlalchemy.orm import sessionmaker
        except ImportError as e:
            logger.debug("Governed indexing imports unavailable: %s", e)
            return

        # Verify this is a governed run
        try:
            with get_session() as gate_session:
                contract = load_run_provenance_contract(gate_session, ctx.db_run_id)
                mode = select_run_execution_mode(contract)
        except Exception:
            return  # Not governed — skip

        if mode != "governed":
            return

        # Use injected governed runtime, or construct from settings
        from backend.pipeline.vector_runtime import build_governed_vector_runtime_from_settings

        if self._governed_runtime is not None:
            runtime = self._governed_runtime
        else:
            engine = _get_engine()
            runtime = build_governed_vector_runtime_from_settings(engine)
            if runtime is None:
                logger.warning("Cannot construct governed vector runtime for indexing")
                return

        profile_id = runtime.embedding_profile_id
        profile_dict = runtime.profile_dict
        Session = runtime.session_factory
        backend = runtime.backend

        # Index each paper
        indexed = 0
        failed = 0
        already = 0
        for paper in papers:
            doc = build_title_abstract_document(
                paper_id=0,  # Will be resolved from DB — use source_id lookup
                title=paper.title,
                abstract=getattr(paper, "abstract", None),
                embedding_profile_id=profile_id,
            )

            # Resolve the canonical DB paper ID from the search-layer paper
            try:
                from backend.db import crud
                with get_session() as s:
                    db_paper = crud.get_paper_by_source_id(s, paper.id)
                    if db_paper is None:
                        logger.debug("Paper %s not in DB yet — skipping governed index", paper.id)
                        failed += 1
                        continue
                    db_paper_id = db_paper.id

                # Rebuild doc with correct paper_id
                doc = build_title_abstract_document(
                    paper_id=db_paper_id,
                    title=paper.title,
                    abstract=getattr(paper, "abstract", None),
                    embedding_profile_id=profile_id,
                )

                # Use the embedding service to generate the embedding
                class _EmbeddingAdapter:
                    """Adapts EmbeddingService to the indexer's embed_single interface."""
                    def __init__(self, embedding_service):
                        self._svc = embedding_service
                    async def embed_single(self, text):
                        result = await self._svc.embed_texts([text])
                        return result[0] if result else []

                outcome = await index_document(
                    session_factory=Session,
                    backend=backend,
                    embedding_provider=_EmbeddingAdapter(self._embedding),
                    profile=profile_dict,
                    document=doc,
                )
                if outcome.status == "indexed":
                    indexed += 1
                elif outcome.status == "already_indexed":
                    already += 1
            except Exception as e:
                logger.debug("Governed indexing failed for paper %s: %s", paper.id, e)
                failed += 1

        logger.info(
            "Governed indexing: %d indexed, %d already-indexed, %d failed (of %d papers)",
            indexed, already, failed, len(papers),
        )


class GapAnalysisStage(PipelineStage):
    def __init__(self, gap_analyzer, goal_manager, hooks, memory, kg=None, faithfulness_checker=None):
        self._gap_analyzer = gap_analyzer
        self._goal_manager = goal_manager
        self._hooks = hooks
        self._memory = memory
        self._kg = kg
        self._faithfulness_checker = faithfulness_checker

    @property
    def name(self) -> str:
        return "gap_analysis"

    async def execute(self, ctx: StageContext) -> bool:
        return await self._execute_gap_analysis(ctx, provider=ctx.provider_override, receipts=ctx.receipts)

    async def _execute_gap_analysis(self, ctx: StageContext, *, provider=None, receipts=None) -> bool:
        # Brief pause to let API rate limiter cool after ingestion burst
        # Reduced from 15s to 2s since gap analysis now uses local LM Studio
        await asyncio.sleep(2.0)

        prior_gaps = await self._recall_prior_gaps(ctx.domain)
        gaps, cluster_report = await self._gap_analyzer.analyze(
            ctx.all_papers,
            domain=ctx.domain,
            max_gaps=ctx.max_gaps,
            prior_gaps=prior_gaps,
            provider=provider,
            receipts=receipts,
        )
        ctx.result.gaps = gaps
        ctx.result.cluster_report = cluster_report
        logger.info("Identified %d research gaps", len(gaps))

        # Write gaps to Knowledge Graph
        if self._kg:
            from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
            from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
            from backend.pipeline.knowledge.truth import TruthValue

            for gap in gaps:
                gap_entity = KnowledgeEntity(
                    id=f"gap:{gap.title[:60]}",
                    entity_type=EntityType.CONCEPT,
                    name=gap.title,
                    properties={
                        "gap_type": gap.gap_type,
                        "description": gap.description[:200],
                        "potential_impact": gap.potential_impact,
                    },
                    truth=TruthValue(frequency=gap.confidence, confidence=0.6),
                )
                self._kg.add_entity(gap_entity)
            self._kg.save()
            logger.info("Added %d gap entities to Knowledge Graph", len(gaps))

            # G3: Revise gap truth based on paper overlap
            if ctx.all_papers:
                for gap in gaps:
                    gap_eid = f"gap:{gap.title[:60]}"
                    # Count papers whose title/abstract overlap with gap description
                    overlap_count = 0
                    gap_words = set(gap.description.lower().split()[:20])
                    for paper in ctx.all_papers:
                        paper_text = f"{paper.title} {paper.abstract or ''}".lower()
                        if sum(1 for w in gap_words if w in paper_text) >= 3:
                            overlap_count += 1
                    if overlap_count > 0:
                        entity = self._kg._entities.get(gap_eid)
                        if entity and hasattr(entity, 'truth'):
                            from backend.pipeline.knowledge.truth import TruthValue
                            revised = entity.truth.revise(
                                TruthValue(
                                    frequency=min(0.95, 0.5 + overlap_count * 0.05),
                                    confidence=0.6,
                                    evidence_count=overlap_count,
                                )
                            )
                            entity.truth = revised
                            logger.debug(
                                "Revised gap truth for '%s': %d overlapping papers → confidence %.3f",
                                gap.title[:40], overlap_count, revised.confidence,
                            )
                self._kg.save()

        # Faithfulness check: verify gap claims against source papers
        if self._faithfulness_checker and gaps:
            try:
                reports = await self._faithfulness_checker.check_gap_claims(
                    gaps, ctx.all_papers,
                )
                unfaithful = [r for r in reports if not r.is_faithful]
                if unfaithful:
                    logger.warning(
                        "Faithfulness check: %d/%d gaps have unfaithful claims",
                        len(unfaithful), len(gaps),
                    )
                    for r in unfaithful:
                        logger.warning("  Unfaithful: %s — %s", r.claim[:60], r.explanation[:100])
            except Exception as e:
                logger.warning("Faithfulness check failed: %s", e)

        if self._goal_manager and gaps:
            new_goals = self._goal_manager.create_from_gaps(gaps)
            logger.info("Created %d research goals from gaps", len(new_goals))

        for gap in gaps:
            await self._hooks.dispatch_sync_safe(
                "gap.found",
                {
                    "title": gap.title,
                    "confidence": gap.confidence,
                    "gap_type": gap.gap_type,
                },
            )
        return True

    async def _recall_prior_gaps(self, domain):
        if not self._memory:
            return None
        from backend.pipeline.memory.models import MemoryQuery, MemoryType

        results = await self._memory.recall(
            MemoryQuery(
                query=f"{domain} research gaps",
                memory_type=MemoryType.SEMANTIC,
                namespace="research_facts",
                top_k=20,
            )
        )
        return results if results else None


class IdeaGenerationStage(PipelineStage):
    def __init__(self, agent, hooks, dag_executor=None, dag_agents=None, provider=None, kg=None, forest=None, reasoning_verifier=None):
        self._agent = agent
        self._hooks = hooks
        self._dag_executor = dag_executor
        self._dag_agents = dag_agents
        self._provider = provider
        self._kg = kg
        self._forest = forest
        self._reasoning_verifier = reasoning_verifier

    @property
    def name(self) -> str:
        return "idea_generation"

    async def execute(self, ctx: StageContext) -> bool:
        provider = ctx.provider_override or self._provider
        if self._dag_executor is not None:
            return await self._execute_dag(ctx, provider)
        return await self._execute_sequential(ctx, provider=provider)

    async def _execute_sequential(self, ctx: StageContext, *, provider=None, receipts=None) -> bool:
        logger.info("Idea Generation (%d rounds, %d ideas/round)", ctx.rounds, ctx.ideas_per)
        ideas = await self._agent.run(
            gaps=ctx.result.gaps,
            context_papers=ctx.all_papers[:30],
            rounds=ctx.rounds,
            ideas_per_round=ctx.ideas_per,
            provider=provider,
            receipts=ctx.receipts if receipts is None else receipts,
        )
        ctx.result.ideas = ideas
        ctx.result.critique_history = self._agent.last_critique_history
        ctx.result.refinement_history = self._agent.last_refinement_history
        logger.info("Generated %d research ideas", len(ideas))

        # Write ideas to Knowledge Graph
        if self._kg and ideas:
            from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
            from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
            from backend.pipeline.knowledge.truth import TruthValue

            for idea in ideas:
                idea_entity = KnowledgeEntity(
                    id=f"idea:{idea.title[:60]}",
                    entity_type=EntityType.CONCEPT,
                    name=idea.title,
                    properties={
                        "proposed_method": idea.proposed_method[:200],
                        "domain": idea.domain,
                    },
                    truth=TruthValue(frequency=idea.score, confidence=0.5),
                )
                self._kg.add_entity(idea_entity)

                for gap_id in idea.source_gap_ids:
                    gap_eid = f"gap:{gap_id[:60]}"
                    if gap_eid in self._kg._entities:
                        self._kg.add_relationship(KnowledgeRelationship(
                            source_id=gap_eid,
                            target_id=f"idea:{idea.title[:60]}",
                            relation_type=RelationType.PROPOSES_METHOD,
                            truth=TruthValue.from_observation(frequency=idea.score),
                        ))

                        # Fix #5: Revise gap truth upward when an idea addresses it
                        gap_entity = self._kg._entities[gap_eid]
                        if hasattr(gap_entity, 'truth') and gap_entity.truth:
                            revised = gap_entity.truth.revise(
                                TruthValue.from_observation(frequency=0.8)
                            )
                            gap_entity.truth = revised
                            logger.debug(
                                "Revised gap truth for '%s': confidence %.3f → %.3f, evidence %d → %d",
                                gap_entity.name[:40],
                                gap_entity.truth.confidence if hasattr(gap_entity, '_prev_conf') else 0.5,
                                revised.confidence,
                                gap_entity.truth.evidence_count if hasattr(gap_entity, '_prev_ev') else 1,
                                revised.evidence_count,
                            )

            self._kg.save()
            logger.info("Added %d idea entities to Knowledge Graph", len(ideas))

        # Reasoning verification on top ideas
        if self._reasoning_verifier and ideas and ctx.result.gaps:
            try:
                for idea in ideas[:5]:
                    gap = ctx.result.gaps[0] if ctx.result.gaps else None
                    if gap:
                        result = await self._reasoning_verifier.verify_idea_reasoning(idea, gap)
                        if not result.passed:
                            logger.warning(
                                "Idea '%s' failed reasoning verification: %s",
                                idea.title[:60], "; ".join(result.issues[:3]),
                            )
            except Exception as e:
                logger.warning("Reasoning verification failed: %s", e)

        for idea in ideas:
            await self._hooks.dispatch_sync_safe(
                "idea.generated",
                {
                    "title": idea.title,
                    "score": idea.score,
                },
            )
        return True

    async def _execute_dag(self, ctx: StageContext, provider=None) -> bool:
        """Execute idea generation via the DAG executor."""
        from backend.pipeline.generation.agent_handlers import register_all_agents
        from backend.pipeline.generation.context_isolator import ContextIsolator
        from backend.pipeline.generation.models import ResearchIdea

        logger.info("Idea Generation via DAG (%d gaps)", len(ctx.result.gaps))

        isolator = ContextIsolator(ctx.result.gaps, ctx.all_papers[:30])

        # Register handlers for this run
        cleanup = register_all_agents(
            registry=self._dag_executor._registry,
            agents=self._dag_agents,
            isolator=isolator,
            provider=provider or self._provider,
        )

        # Prepare input: one item per gap
        dag_input = [
            {"gap": gap, "papers": ctx.all_papers[:30], "n_ideas": ctx.ideas_per}
            for gap in ctx.result.gaps
        ]

        try:
            results = await self._dag_executor.execute(dag_input)
        finally:
            # Restore buffered taxonomies
            for _, buffered, restore in cleanup:
                restore()

        # Extract ResearchIdea objects from results
        ideas = [i for i in results if isinstance(i, ResearchIdea)]
        if not ideas:
            # Try extracting from dicts
            for r in results:
                if isinstance(r, dict) and "ideas" in r:
                    ideas.extend(r["ideas"])

        ctx.result.ideas = ideas
        logger.info("DAG generated %d research ideas", len(ideas))

        for idea in ideas:
            await self._hooks.dispatch_sync_safe(
                "idea.generated",
                {"title": idea.title, "score": idea.score},
            )
        return True


class NoveltyCheckingStage(PipelineStage):
    def __init__(self, novelty_checker, hooks=None):
        self._novelty = novelty_checker
        self._hooks = hooks

    @property
    def name(self) -> str:
        return "novelty_checking"

    async def execute(self, ctx: StageContext) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True
        for i, idea in enumerate(ideas):
            profile, directives = await self._novelty.check_novelty(
                idea,
                run_id=ctx.db_run_id,
                db_engine=__import__("backend.db.database", fromlist=["_get_engine"])._get_engine() if ctx.db_run_id else None,
            )

            # Write BOTH formats for backward compat
            ctx.result.novelty_profiles[i] = profile
            ctx.result.downstream_directives[i] = directives

            # Legacy NoveltyReport for persistence/frontend
            ctx.result.novelty_reports[i] = NoveltyReport(
                overall_score=profile.overall_score,
                method_novelty=next((a.score for a in profile.axes if a.axis.value == "method"), 0.5),
                problem_novelty=next((a.score for a in profile.axes if a.axis.value == "problem"), 0.5),
                domain_transfer=next((a.score for a in profile.axes if a.axis.value == "combination"), 0.5),
                combination_novelty=next((a.score for a in profile.axes if a.axis.value == "contribution"), 0.5),
                novelty_arguments=profile.novelty_arguments,
                closest_matches=[
                    {"title": pw.paper_title, "id": pw.paper_id, "distance": 1.0 - pw.similarity}
                    for pw in profile.closest_prior_work
                ],
            )

            logger.info(
                "Novelty for '%s': %.2f (%s, confidence=%.2f)",
                idea.title[:50], profile.overall_score,
                profile.strategic_direction.value, profile.overall_confidence,
            )

        if self._hooks:
            for i, idea in enumerate(ideas):
                nr = ctx.result.novelty_reports.get(i)
                if nr:
                    await self._hooks.dispatch_sync_safe(
                        "idea.scored",
                        {
                            "title": idea.title,
                            "novelty_score": nr.overall_score,
                        },
                    )
        return True


class FeasibilityScoringStage(PipelineStage):
    def __init__(self, feasibility_scorer):
        self._feasibility = feasibility_scorer

    @property
    def name(self) -> str:
        return "feasibility_scoring"

    async def execute(self, ctx: StageContext) -> bool:
        return await self._execute_feasibility(ctx, provider=ctx.provider_override, receipts=ctx.receipts)

    async def _execute_feasibility(self, ctx: StageContext, *, provider=None, receipts=None) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True
        from backend.config import get_settings
        settings = get_settings()
        for i, idea in enumerate(ideas):
            novelty = ctx.result.novelty_reports.get(i)
            directives = ctx.result.downstream_directives.get(i)
            weight_overrides = None
            if directives and directives.feasibility_weight_overrides:
                weight_overrides = directives.feasibility_weight_overrides
            report = await self._feasibility.score_feasibility(
                idea, novelty,
                weight_overrides=weight_overrides,
                provider=provider,
                receipts=receipts,
            )
            # Counterfactual analysis (Gap 14)
            if settings.counterfactual_enabled:
                report = await self._feasibility.run_counterfactual(report)
            ctx.result.feasibility_reports[i] = report
            logger.info(
                "Feasibility score for '%s': %.1f/10", idea.title[:50], report.overall_score
            )
        return True


class ProposalSynthesisStage(PipelineStage):
    def __init__(
        self, synthesizer, governance_validator=None, governance_audit=None, ref_validator=None
    ):
        self._synthesizer = synthesizer
        self._governance_validator = governance_validator
        self._governance_audit = governance_audit
        self._ref_validator = ref_validator

    @property
    def name(self) -> str:
        return "proposal_synthesis"

    async def execute(self, ctx: StageContext) -> bool:
        return await self._execute_synthesis(ctx, provider=ctx.provider_override, receipts=ctx.receipts)

    async def _execute_synthesis(self, ctx: StageContext, *, provider=None, receipts=None) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True

        # Per-proposal timeout from settings (capped at 300s by HB-01)
        from backend.config import get_settings

        timeout = min(
            getattr(get_settings(), "per_proposal_timeout", 120.0),
            300.0,
        )

        for i, idea in enumerate(ideas):
            novelty = ctx.result.novelty_reports.get(i)
            feasibility = ctx.result.feasibility_reports.get(i)
            directives = ctx.result.downstream_directives.get(i)
            framing = directives.synthesis_framing_directive if directives else ""
            try:
                proposal = await asyncio.wait_for(
                    self._synthesizer.synthesize(
                        idea=idea,
                        novelty_report=novelty,
                        feasibility_report=feasibility,
                        supporting_papers=ctx.all_papers[:30],
                        gaps=ctx.result.gaps,
                        framing_directive=framing,
                        provider=provider,
                        receipts=receipts,
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Proposal synthesis timed out after %.1fs for idea %d: %s",
                    timeout, i + 1, idea.title[:50],
                )
                proposal = ResearchProposal(
                    title=idea.title,
                    abstract=f"Synthesis timed out after {timeout:.0f}s",
                    introduction="Timed out",
                    proposed_method=idea.proposed_method,
                )

            if self._governance_validator:
                proposal_md = proposal.to_markdown()
                validated_text, checks = await self._governance_validator.validate_with_reask(
                    proposal_md,
                    output_type="proposal",
                )
                proposal.sections["validated_text"] = validated_text

                if self._governance_audit:
                    from backend.pipeline.governance.events import (
                        GovernanceAuditLog,
                        GovernanceEvent,
                    )

                    verdict = (
                        "accepted"
                        if all(c.verdict.value != "rejected" for c in checks)
                        else "revised"
                    )
                    self._governance_audit.record(
                        GovernanceEvent(
                            event_type=f"output.{verdict}",
                            stage="proposal_synthesis",
                            content_hash=GovernanceAuditLog.content_hash(proposal_md),
                            checks_summary=f"{len(checks)} checks, verdict={verdict}",
                        )
                    )

            ctx.result.proposals[i] = proposal
            logger.info("Generated proposal for idea %d: %s", i + 1, idea.title[:50])

            # Reference validation
            if self._ref_validator:
                refs = proposal.sections.get("references", [])
                if isinstance(refs, list) and refs:
                    validation_results = await self._ref_validator.validate(refs)
                    proposal.sections["reference_validation"] = [
                        {"index": v.reference_index, "title": v.title, "status": v.status}
                        for v in validation_results
                    ]
                    unverified = sum(1 for v in validation_results if v.status == "unverified")
                    if unverified:
                        logger.info(
                            "Proposal %d: %d/%d references unverified",
                            i + 1,
                            unverified,
                            len(refs),
                        )
        return True


class TreeSearchStage(PipelineStage):
    """Pipeline stage that uses TreeSearchEngine for beam-search idea generation.

    Replaces IdeaGenerationStage when tree_of_thought_enabled=True (HB-01).
    The stage name is "idea_generation" so it occupies the same slot in
    STAGE_ORDER — all downstream persistence/checkpoint logic works unchanged.
    """

    # HB-03: Maximum serialized tree_data size in bytes (500KB)
    MAX_TREE_DATA_BYTES = 500 * 1024

    def __init__(
        self,
        engine: "TreeSearchEngine",
        hooks,
        provider=None,
        kg=None,
    ) -> None:
        self._engine = engine
        self._hooks = hooks
        self._provider = provider
        self._kg = kg

    @property
    def name(self) -> str:
        return "idea_generation"

    async def execute(self, ctx: StageContext) -> bool:
        logger.info(
            "TreeSearchStage: beam search (depth=%d, beam_width=%d)",
            self._engine.config.max_depth,
            self._engine.config.beam_width,
        )

        # Run beam search
        raw_ideas = await self._engine.search(
            gaps=ctx.result.gaps,
            context_papers=ctx.all_papers[:30],
        )

        # BATCH-75/TASK-01: Convert IdeaCandidate → ResearchIdea (HB-01)
        ideas = self._convert_to_research_ideas(raw_ideas)
        assert all(isinstance(i, ResearchIdea) for i in ideas), (
            "HB-01 violation: TreeSearchStage must assign only ResearchIdea to ctx.result.ideas"
        )

        ctx.result.ideas = ideas
        logger.info("TreeSearchStage: generated %d ideas via tree search", len(ideas))

        # Serialize tree structure into tree_data for frontend (AC-01-03)
        tree_data = self._build_tree_data(ideas)
        ctx.result.tree_data = self._enforce_size_limit(tree_data)  # HB-03

        # Write ideas to Knowledge Graph (same as IdeaGenerationStage)
        if self._kg and ideas:
            from backend.pipeline.knowledge.entities import EntityType, KnowledgeEntity
            from backend.pipeline.knowledge.relationships import KnowledgeRelationship, RelationType
            from backend.pipeline.knowledge.truth import TruthValue

            for idea in ideas:
                idea_entity = KnowledgeEntity(
                    id=f"idea:{idea.title[:60]}",
                    entity_type=EntityType.CONCEPT,
                    name=idea.title,
                    properties={
                        "proposed_method": idea.proposed_method[:200],
                    },
                    truth=TruthValue(frequency=getattr(idea, 'overall_score', 0.5), confidence=0.5),
                )
                self._kg.add_entity(idea_entity)

                for gap_id in getattr(idea, 'source_gap_ids', []):
                    gap_eid = f"gap:{gap_id[:60]}"
                    if gap_eid in self._kg._entities:
                        self._kg.add_relationship(KnowledgeRelationship(
                            source_id=gap_eid,
                            target_id=f"idea:{idea.title[:60]}",
                            relation_type=RelationType.PROPOSES_METHOD,
                            truth=TruthValue.from_observation(frequency=getattr(idea, 'overall_score', 0.5)),
                        ))

                        # Fix #5: Revise gap truth upward when an idea addresses it
                        gap_entity = self._kg._entities[gap_eid]
                        if hasattr(gap_entity, 'truth') and gap_entity.truth:
                            revised = gap_entity.truth.revise(
                                TruthValue.from_observation(frequency=0.8)
                            )
                            gap_entity.truth = revised

            self._kg.save()
            logger.info("Added %d idea entities to Knowledge Graph (tree search)", len(ideas))

        # Dispatch hooks
        for idea in ideas:
            await self._hooks.dispatch_sync_safe(
                "idea.generated",
                {
                    "title": idea.title,
                    "score": getattr(idea, 'score', getattr(idea, 'overall_score', 0.0)),
                },
            )
        return True

    # ── BATCH-75/TASK-01: IdeaCandidate → ResearchIdea conversion ──────

    @staticmethod
    def _convert_to_research_ideas(candidates: list) -> list[ResearchIdea]:
        """Convert IdeaCandidate objects to ResearchIdea with safe defaults.

        Handles field mapping for fields that IdeaCandidate lacks
        (domain, round_generated, supporting_papers, source_gap_ids).

        Conversion map:
            title                     → title
            problem_statement         → problem_statement
            proposed_method            → proposed_method
            expected_contributions    → expected_contributions (default "")
            novelty_rationale         → novelty_rationale (default "")
            evaluation_approach       → evaluation_approach (default "")
            overall_score             → score
            parent_idea_ids           → source_gap_ids (best-effort; default [])
            (no equivalent)           → domain = "AI/NLP"
            (no equivalent)           → round_generated = 1
            (no equivalent)           → supporting_papers = []
        """
        results: list[ResearchIdea] = []
        for c in candidates:
            research_idea = ResearchIdea(
                title=c.title,
                problem_statement=c.problem_statement,
                proposed_method=c.proposed_method,
                expected_contributions=getattr(c, "expected_contributions", "") or "",
                novelty_rationale=getattr(c, "novelty_rationale", "") or "",
                evaluation_approach=getattr(c, "evaluation_approach", "") or "",
                domain="AI/NLP",
                round_generated=1,
                score=getattr(c, "overall_score", 0.0),
                supporting_papers=[],
                source_gap_ids=getattr(c, "parent_idea_ids", []) or [],
            )
            results.append(research_idea)
        return results

    def _build_tree_data(self, ideas: list) -> dict:
        """Build a serializable tree structure from generated ideas.

        The tree is reconstructed from the ideas' parent_idea_ids lineage
        fields, producing a flat node list with parent references that the
        frontend can render as an SVG tree.
        """
        nodes: list[dict] = []
        for idea in ideas:
            # BATCH-75/TASK-01: getattr guards — ResearchIdea lacks .id
            # and .parent_idea_ids (CHK-16/CHK-17)
            idea_id = getattr(idea, 'id', idea.title[:60])
            parent_ids = getattr(
                idea, 'parent_idea_ids',
                getattr(idea, 'source_gap_ids', [])
            )
            nodes.append({
                "id": idea_id,
                "title": idea.title,
                "score": getattr(idea, 'overall_score', getattr(idea, 'score', 0.0)),
                "proposed_method": idea.proposed_method[:200],
                "parent_ids": parent_ids or [],
            })

        return {
            "engine": "tree_search",
            "config": {
                "beam_width": self._engine.config.beam_width,
                "max_depth": self._engine.config.max_depth,
                "ideas_per_node": self._engine.config.ideas_per_node,
            },
            "nodes": nodes,
        }

    @classmethod
    def _enforce_size_limit(cls, tree_data: dict) -> dict | None:
        """Enforce 500KB limit on tree_data (HB-03).

        If serialized JSON exceeds the limit, truncate nodes to fit.
        Returns None if even an empty tree would exceed the limit (shouldn't happen).
        """
        serialized = json.dumps(tree_data, default=str)
        if len(serialized.encode("utf-8")) <= cls.MAX_TREE_DATA_BYTES:
            return tree_data

        # Try progressive truncation of nodes list
        nodes = tree_data.get("nodes", [])
        if isinstance(nodes, list):
            for trim_size in [len(nodes) // 2, len(nodes) // 4, 0]:
                tree_data_copy = dict(tree_data)
                tree_data_copy["nodes"] = nodes[:trim_size]
                serialized = json.dumps(tree_data_copy, default=str)
                if len(serialized.encode("utf-8")) <= cls.MAX_TREE_DATA_BYTES:
                    logger.warning(
                        "TreeSearchStage: tree_data truncated to %d nodes (HB-03: 500KB limit)",
                        trim_size,
                    )
                    return tree_data_copy

        logger.error("TreeSearchStage: tree_data exceeds 500KB even when empty — returning None")
        return None


class MechanicalMetricsStage(PipelineStage):
    """Compute objective mechanical metrics for each idea (BATCH-64).

    Runs after feasibility scoring so that all prior data (ideas, papers,
    gaps, novelty/feasibility reports) is available.  Metrics are stored
    on ``ctx.result.mechanical_metrics`` and merged into the novelty_report
    JSON during persistence — no schema change required.
    """

    def __init__(self):
        self._calculator = None

    @property
    def name(self) -> str:
        return "mechanical_metrics"

    async def execute(self, ctx: StageContext) -> bool:
        ideas = ctx.result.ideas
        if not ideas:
            return True

        from backend.pipeline.evaluation.mechanical_metrics import MechanicalMetricsCalculator

        if self._calculator is None:
            self._calculator = MechanicalMetricsCalculator()

        for i, idea in enumerate(ideas):
            try:
                # Build supporting_papers for this idea
                cited_ids = set(getattr(idea, "supporting_papers", []) or [])
                supporting = [p for p in ctx.all_papers if getattr(p, "id", None) in cited_ids]

                # Fallback: if no explicit supporting_papers, use all papers
                if not supporting:
                    supporting = ctx.all_papers[:30]

                metrics = self._calculator.compute_all(
                    idea=idea,
                    gaps=ctx.result.gaps,
                    supporting_papers=supporting,
                    all_domain_papers=ctx.all_papers,
                )
                ctx.result.mechanical_metrics[i] = metrics

                # Compute and log composite score (informational)
                novelty = ctx.result.novelty_reports.get(i)
                feasibility = ctx.result.feasibility_reports.get(i)
                llm_score = getattr(idea, "score", 0.0)
                nov_score = novelty.overall_score if novelty else 0.0
                feas_score = (feasibility.overall_score / 10.0) if feasibility else 0.0
                mech_avg = sum(metrics.values()) / len(metrics) if metrics else 0.0
                composite = 0.4 * llm_score + 0.3 * mech_avg + 0.3 * (nov_score + feas_score) / 2
                logger.info(
                    "Mechanical metrics for '%s': composite=%.3f, metrics=%s",
                    idea.title[:50], composite, metrics,
                )
            except Exception as e:
                logger.warning(
                    "Failed to compute mechanical metrics for idea %d: %s", i, e,
                )
        return True


class ExportStage(PipelineStage):
    def __init__(self, export_service):
        self._export = export_service

    @property
    def name(self) -> str:
        return "export"

    async def execute(self, ctx: StageContext) -> bool:
        if ctx.export_format and ctx.result.proposals:
            for i, proposal in ctx.result.proposals.items():
                path = await self._export.export(proposal, format=ctx.export_format)
                ctx.result.export_paths[i] = path
                logger.info("Exported proposal to: %s", path)

        # Post-run knowledge indexing (B158)
        try:
            from backend.pipeline.knowledge.integration import KnowledgeIntegrationService
            domain = getattr(ctx, 'domain', '') or 'unknown'
            service = KnowledgeIntegrationService()
            counts = service.index_run_results(
                domain=domain,
                papers=getattr(ctx.result, 'papers', None) or getattr(ctx, 'all_papers', None),
                gaps=getattr(ctx.result, 'gaps', None),
                ideas=getattr(ctx.result, 'ideas', None),
                run_id=getattr(ctx, 'run_id', ''),
            )
            if counts.get("total", 0) > 0:
                logger.info(
                    "Knowledge library indexed: %d papers, %d gaps, %d ideas for '%s'",
                    counts.get("papers", 0), counts.get("gaps", 0), counts.get("ideas", 0), domain,
                )
            service.close()
        except Exception as e:
            logger.warning("Knowledge library indexing failed (non-fatal, HB-02): %s", e)

        # B162: Journal note for export
        if ctx.journal:
            try:
                export_count = len(ctx.result.export_paths) if ctx.result.export_paths else 0
                ctx.journal.add_note("export", f"Exported {export_count} proposal(s)", {
                    "export_count": export_count,
                    "format": ctx.export_format,
                })
            except Exception:
                pass

        return True


class AdversarialReviewStage(PipelineStage):
    """Adversarial cross-model review of proposals with revision loop.

    Routes proposals through a different model family for critical scoring.
    Rejected proposals (overall < 7.0) receive revision notes and are
    re-synthesized. Max 2 revision rounds (HB-04).

    HB-02: Skips review if reviewer provider == synthesizer provider.
    HB-03: Graceful fallback on LLM failure — marks proposal as skipped.
    """

    MAX_REVISION_ROUNDS = 2
    PASS_THRESHOLD = 7.0

    def __init__(
        self,
        reviewer,
        synthesizer,
        generation_provider=None,
        thinking_provider=None,
    ):
        from backend.pipeline.evaluation.adversarial_reviewer import AdversarialReviewer
        self._reviewer: AdversarialReviewer = reviewer
        self._synthesizer = synthesizer
        self._generation_provider = generation_provider
        self._thinking_provider = thinking_provider

    @property
    def name(self) -> str:
        return "adversarial_review"

    async def execute(self, ctx: StageContext) -> bool:
        # HB-02: Skip if both providers are genuinely the same model on the same endpoint.
        # Compare base_url + model instead of provider_name (which is always "anthropic"
        # because both providers use AnthropicProvider class internally).
        # Must unwrap ResilientProvider to access the inner provider's attributes.
        def _unwrap(provider):
            """Unwrap ResilientProvider or CircuitBreakerProxy to get the real provider."""
            visited = set()
            max_depth = 10
            for _ in range(max_depth):
                if not hasattr(provider, "_wrapped"):
                    break
                if id(provider) in visited:
                    break
                visited.add(id(provider))
                provider = provider._wrapped
            return provider

        tp_raw = _unwrap(self._thinking_provider) if self._thinking_provider else None
        gp_raw = _unwrap(self._generation_provider) if self._generation_provider else None

        if tp_raw and gp_raw:
            thinking_url = (
                getattr(tp_raw, "base_url", None)
                or getattr(tp_raw, "_base_url", None)
                or getattr(getattr(tp_raw, "_client", None), "base_url", None)
                or ""
            )
            generation_url = (
                getattr(gp_raw, "base_url", None)
                or getattr(gp_raw, "_base_url", None)
                or getattr(getattr(gp_raw, "_client", None), "base_url", None)
                or ""
            )
            thinking_model = getattr(tp_raw, "default_model", None) or getattr(tp_raw, "_model", None) or ""
            generation_model = getattr(gp_raw, "default_model", None) or getattr(gp_raw, "_model", None) or ""

            # Same endpoint AND same model = self-play
            if thinking_url == generation_url and thinking_model == generation_model:
                logger.warning(
                    "HB-02: Thinking (%s @ %s) == Generation (%s @ %s) - "
                    "skipping adversarial review to avoid self-play",
                    thinking_model, thinking_url, generation_model, generation_url,
                )
                return True
            logger.info(
                "Adversarial review: thinking=%s @ %s vs generation=%s @ %s (different providers)",
                thinking_model, thinking_url, generation_model, generation_url,
            )

        if not ctx.result.proposals:
            return True

        for idx, proposal in list(ctx.result.proposals.items()):
            try:
                await self._review_proposal(idx, proposal, ctx)
            except Exception as e:
                logger.warning(
                    "Adversarial review failed for proposal %d (non-fatal, HB-03): %s",
                    idx, e,
                )
                metadata = self._get_metadata(proposal)
                metadata["adversarial_review"] = {
                    "status": "skipped",
                    "reason": str(e),
                }
                self._set_metadata(proposal, metadata)

        return True

    async def _review_proposal(
        self, idx: int, proposal, ctx: StageContext,
    ) -> None:
        """Review a single proposal with revision loop."""
        proposal_text = proposal.to_markdown() if hasattr(proposal, "to_markdown") else str(proposal)
        source_papers = [
            f"{p.title}: {getattr(p, 'abstract', '')}"
            for p in ctx.all_papers[:10]
        ]

        # Determine context window from provider or gateway
        context_window = 8192
        try:
            from backend.config import get_settings
            settings = get_settings()
            # The gateway may have probed a different context
        except Exception:
            pass

        for round_num in range(1, self.MAX_REVISION_ROUNDS + 2):  # 1..3
            score = await self._reviewer.review(
                proposal_text=proposal_text,
                source_papers=source_papers,
                round_num=round_num,
                context_window=context_window,
            )

            # Store score in metadata
            metadata = self._get_metadata(proposal)
            metadata["adversarial_review"] = score.to_dict()
            self._set_metadata(proposal, metadata)

            if score.overall >= self.PASS_THRESHOLD:
                logger.info(
                    "Proposal %d passed adversarial review (round %d, overall=%.1f)",
                    idx, round_num, score.overall,
                )
                return  # Accepted

            if score.revision_notes and round_num <= self.MAX_REVISION_ROUNDS:
                logger.info(
                    "Proposal %d rejected (round %d, overall=%.1f) — re-synthesizing",
                    idx, round_num, score.overall,
                )
                # Re-synthesize using ONLY revision notes (A-02)
                try:
                    proposal = await self._re_synthesize(
                        proposal, score.revision_notes, ctx, idx,
                    )
                    proposal_text = (
                        proposal.to_markdown()
                        if hasattr(proposal, "to_markdown")
                        else str(proposal)
                    )
                except Exception as e:
                    logger.warning(
                        "Re-synthesis failed for proposal %d (non-fatal): %s", idx, e,
                    )
                    break
            else:
                # Max revisions reached or no revision notes
                break

        # After loop: accept with current scores + max_revisions_reached flag
        metadata = self._get_metadata(proposal)
        review_data = metadata.get("adversarial_review", {})
        review_data["max_revisions_reached"] = True
        metadata["adversarial_review"] = review_data
        self._set_metadata(proposal, metadata)
        # Write back to context so tests/callers see updated proposal
        ctx.result.proposals[idx] = proposal
        logger.info(
            "Proposal %d accepted after max revisions (overall=%.1f)",
            idx, review_data.get("overall", 0.0),
        )

    async def _re_synthesize(
        self,
        proposal,
        revision_notes: str,
        ctx: StageContext,
        idx: int,
    ):
        """Re-synthesize proposal using revision notes as the ONLY input (A-02)."""
        # Build minimal idea from proposal for re-synthesis
        from backend.pipeline.generation.models import ResearchIdea
        idea = ResearchIdea(
            title=proposal.title if hasattr(proposal, "title") else f"Proposal {idx}",
            problem_statement=proposal.sections.get("introduction", "")[:500]
            if hasattr(proposal, "sections") and isinstance(proposal.sections, dict)
            else "",
            proposed_method=proposal.sections.get("proposed_method", "")[:500]
            if hasattr(proposal, "sections") and isinstance(proposal.sections, dict)
            else "",
            expected_contributions=revision_notes,  # A-02: only revision notes
            novelty_rationale="",
            evaluation_approach="",
            domain=ctx.domain,
            round_generated=1,
            score=0.0,
            supporting_papers=[],
            source_gap_ids=[],
        )
        new_proposal = await self._synthesizer.synthesize(
            idea=idea,
            novelty_report=None,
            feasibility_report=None,
            supporting_papers=ctx.all_papers[:30],
            gaps=ctx.result.gaps,
            provider=ctx.provider_override,
            receipts=ctx.receipts,
        )
        # Copy over sections from re-synthesized proposal
        if hasattr(new_proposal, "sections") and hasattr(proposal, "sections"):
            proposal.sections.update(new_proposal.sections)
        return proposal

    @staticmethod
    def _get_metadata(proposal) -> dict:
        """Get metadata dict from a proposal, handling JSON string storage."""
        metadata = {}
        if hasattr(proposal, "metadata") and proposal.metadata:
            if isinstance(proposal.metadata, str):
                try:
                    metadata = json.loads(proposal.metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif isinstance(proposal.metadata, dict):
                metadata = proposal.metadata
        return metadata

    @staticmethod
    def _set_metadata(proposal, metadata: dict) -> None:
        """Set metadata dict on a proposal, handling JSON string storage."""
        # Always set the attribute — ResearchProposal may not have metadata initially
        current = getattr(proposal, "metadata", None)
        if isinstance(current, str) or current is None:
            proposal.metadata = json.dumps(metadata)
        else:
            proposal.metadata = metadata


class PaperSynthesisStage(PipelineStage):
    """Expand proposals into full academic papers via LLM.

    Runs after adversarial_review. For each proposal, uses PaperSynthesizer
    to produce a structured academic paper stored in proposal metadata.

    Strategy selection:
    - If prompt fits context → monolithic synthesis (PaperSynthesizer)
    - If prompt overflows → section-wise synthesis (SectionWiseSynthesizer)
    - Section-wise generates outline → each section independently → assemble

    Minimum output policy:
    - paper_synthesis minimum output: 2000 tokens
    - If available output < minimum, skip monolithic and go section-wise

    HB-02: Graceful fallback — logs warning and sets full_paper to None
    on LLM failure. Never blocks the pipeline.
    """

    # Minimum viable output tokens — below this, monolithic synthesis is pointless
    MIN_OUTPUT_TOKENS = 2000

    def __init__(self, provider=None, synthesizer=None, context_window: int = 8192):
        self._provider = provider
        self._synthesizer = synthesizer  # Optional: inject for testing
        self._context_window = context_window

    @property
    def name(self) -> str:
        return "paper_synthesis"

    async def execute(self, ctx: StageContext) -> bool:
        # Check strategy flag
        strategy_config = getattr(ctx, 'params', {}).get('strategy_config', None)
        if strategy_config:
            stage_cfg = strategy_config.stages.get('paper_synthesis')
            if stage_cfg and not stage_cfg.enabled:
                logger.info("Paper synthesis disabled by strategy — skipping")
                return True

        if not ctx.result.proposals:
            return True

        # Resolve provider — use generation provider (A-01)
        provider = ctx.provider_override or self._provider
        if not provider:
            try:
                from backend.config import get_settings
                from backend.providers.provider_factory import get_generation_provider
                provider = get_generation_provider(get_settings())
            except Exception as e:
                logger.warning("Cannot resolve generation provider for paper synthesis: %s", e)
                return True

        from backend.pipeline.synthesis.paper_synthesizer import PaperSynthesizer
        from backend.pipeline.synthesis.section_wise_synthesizer import SectionWiseSynthesizer

        # Determine context window from gateway if available
        context_window = self._context_window
        try:
            from backend.config import get_settings
            settings = get_settings()
            # The gateway may have probed a larger context
            if hasattr(self, '_context_window'):
                context_window = self._context_window
        except Exception:
            pass

        # Format source papers for citation
        source_papers = []
        for idx, p in enumerate(ctx.all_papers[:30], 1):
            authors = getattr(p, 'authors', None)
            if authors:
                author_str = ", ".join(
                    getattr(a, 'name', str(a)) for a in (authors[:3] if hasattr(authors, '__getitem__') else authors)
                )
            else:
                author_str = "Unknown"
            line = (
                f"[SOURCE-{idx}] {author_str} "
                f"({getattr(p, 'year', 'n.d.')}). "
                f"{getattr(p, 'title', 'Untitled')}. "
                f"{getattr(p, 'venue', 'Unknown venue')}."
            )
            abstract = getattr(p, 'abstract', '')
            if abstract:
                line += f"\n  Abstract: {abstract[:500]}"
            source_papers.append(line)

        for idx, proposal in ctx.result.proposals.items():
            try:
                proposal_text = (
                    proposal.to_markdown()
                    if hasattr(proposal, "to_markdown")
                    else str(proposal)
                )

                # Estimate token budget for this proposal
                estimated_input = len(proposal_text) // 3 + sum(len(s) // 3 for s in source_papers)
                safety_margin = int(context_window * 0.85)
                available_output = safety_margin - estimated_input

                # Strategy selection: section-wise if monolithic won't fit
                if available_output < self.MIN_OUTPUT_TOKENS:
                    logger.info(
                        "Paper synthesis: switching to section-wise "
                        "(estimated input=%d, available output=%d < minimum %d)",
                        estimated_input, available_output, self.MIN_OUTPUT_TOKENS,
                    )
                    section_synth = SectionWiseSynthesizer(
                        provider=provider,
                        context_window=context_window,
                    )
                    result = await section_synth.synthesize(
                        proposal_text=proposal_text,
                        source_papers=source_papers,
                        domain=ctx.domain,
                        proposal_id=idx,
                    )
                    # Convert to dict for storage (compatible shape)
                    metadata = self._get_metadata(proposal)
                    metadata["full_paper"] = {
                        "proposal_id": result.proposal_id,
                        "paper_markdown": result.paper_markdown,
                        "word_count": result.word_count,
                        "venue": result.venue,
                        "model_used": result.model_used,
                        "source_count": result.source_count,
                        "sections_generated": result.sections_generated,
                        "sections_total": result.sections_total,
                        "synthesis_strategy": "section_wise",
                    }
                    metadata["synthesis_strategy"] = "section_wise"
                    self._set_metadata(proposal, metadata)
                    logger.info(
                        "Paper synthesis (section-wise) completed for proposal %d: "
                        "%d words, %d/%d sections",
                        idx, result.word_count,
                        result.sections_generated, result.sections_total,
                    )
                else:
                    # Monolithic synthesis — original path
                    synthesizer = self._synthesizer or PaperSynthesizer(provider)
                    result = await synthesizer.synthesize(
                        proposal_text=proposal_text,
                        source_papers=source_papers,
                        domain=ctx.domain,
                        proposal_id=idx,
                    )
                    metadata = self._get_metadata(proposal)
                    if result is not None:
                        result_dict = result.to_dict()
                        result_dict["synthesis_strategy"] = "monolithic"
                        metadata["full_paper"] = result_dict
                        metadata["synthesis_strategy"] = "monolithic"
                        logger.info(
                            "Paper synthesis (monolithic) completed for proposal %d: %d words",
                            idx, result.word_count,
                        )
                    else:
                        metadata["full_paper"] = None
                        logger.warning(
                            "Paper synthesis failed for proposal %d (HB-02)", idx,
                        )
                    self._set_metadata(proposal, metadata)

            except Exception as e:
                logger.warning(
                    "Paper synthesis failed for proposal %d (non-fatal, HB-02): %s",
                    idx, e,
                )
                metadata = self._get_metadata(proposal)
                metadata["full_paper"] = None
                self._set_metadata(proposal, metadata)

        return True

    @staticmethod
    def _get_metadata(proposal) -> dict:
        """Get metadata dict from a proposal, handling JSON string storage."""
        metadata = {}
        if hasattr(proposal, "metadata") and proposal.metadata:
            if isinstance(proposal.metadata, str):
                try:
                    metadata = json.loads(proposal.metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif isinstance(proposal.metadata, dict):
                metadata = proposal.metadata
        return metadata

    @staticmethod
    def _set_metadata(proposal, metadata: dict) -> None:
        """Set metadata dict on a proposal, handling JSON string storage."""
        current = getattr(proposal, "metadata", None)
        if isinstance(current, str) or current is None:
            proposal.metadata = json.dumps(metadata)
        else:
            proposal.metadata = metadata


class ProposalDeepeningStage(PipelineStage):
    """Enriches proposals with architecture, toy examples, failure modes, and criteria."""

    def __init__(self, deepener=None):
        from backend.pipeline.verification.proposal_deepener import ProposalDeepener
        self._deepener = deepener or ProposalDeepener()

    @property
    def name(self) -> str:
        return "proposal_deepening"

    async def execute(self, ctx: StageContext) -> bool:
        """Deepen each proposal in template mode (no LLM needed).

        HB-01: All exceptions caught and logged. Pipeline continues.
        HB-02: Original proposal text is never overwritten.
        """
        try:
            if not ctx.result.proposals:
                logger.debug("No proposals to deepen — skipping")
                return True

            for idx, proposal in ctx.result.proposals.items():
                try:
                    idea_dict = {
                        "id": idx,
                        "title": getattr(proposal, 'title', f'Idea {idx}'),
                        "problem_statement": proposal.sections.get('introduction', '')[:500] if hasattr(proposal, 'sections') and isinstance(proposal.sections, dict) else '',
                        "proposed_method": proposal.sections.get('proposed_method', '')[:500] if hasattr(proposal, 'sections') and isinstance(proposal.sections, dict) else '',
                    }
                    deepened = await self._deepener.deepen(idea_dict)

                    # Store deepened content in proposal metadata (HB-02: don't overwrite text)
                    metadata = {}
                    if hasattr(proposal, 'metadata') and proposal.metadata:
                        try:
                            metadata = json.loads(proposal.metadata) if isinstance(proposal.metadata, str) else proposal.metadata
                        except (json.JSONDecodeError, TypeError):
                            metadata = {}

                    metadata["deepened"] = {
                        "architecture": deepened.architecture,
                        "toy_example": deepened.toy_example,
                        "failure_modes": deepened.failure_modes,
                        "success_criteria": deepened.success_criteria,
                    }

                    if hasattr(proposal, 'metadata'):
                        proposal.metadata = json.dumps(metadata) if not isinstance(metadata, str) else metadata

                    # Also append deepened content as actual proposal sections (for export)
                    if hasattr(proposal, 'sections') and isinstance(proposal.sections, dict):
                        if deepened.architecture:
                            proposal.sections["preliminary_architecture"] = deepened.architecture
                        if deepened.toy_example:
                            proposal.sections["minimal_working_example"] = deepened.toy_example
                        if deepened.failure_modes:
                            proposal.sections["failure_modes"] = deepened.failure_modes
                        if deepened.success_criteria:
                            proposal.sections["success_criteria"] = deepened.success_criteria

                    logger.info(
                        "Deepened proposal %d: '%s'",
                        idx,
                        getattr(proposal, 'title', 'untitled')[:60],
                    )
                except Exception as e:
                    # HB-01: Per-proposal failure is non-fatal
                    logger.warning("Failed to deepen proposal %d (non-fatal): %s", idx, e)

        except Exception as e:
            # HB-01: Overall stage failure is non-fatal
            logger.warning("Proposal deepening stage failed (non-fatal, HB-01): %s", e)

        return True


class CitationAuditStage(PipelineStage):
    """Post-processing audit that verifies citations and quantitative claims.

    Runs after paper_synthesis. For each proposal, audits [SOURCE-X] citations
    against the actual source papers and stores results in proposal metadata.

    HB-02: Graceful fallback on LLM failure — stores status="skipped".
    """

    def __init__(self, provider=None, auditor=None):
        self._provider = provider
        self._auditor = auditor  # Optional: inject for testing

    @property
    def name(self) -> str:
        return "citation_audit"

    async def execute(self, ctx: StageContext) -> bool:
        # Check strategy flag — skip if citation_audit disabled
        strategy_config = getattr(ctx, 'params', {}).get('strategy_config', None)
        if strategy_config:
            stage_cfg = strategy_config.stages.get('citation_audit')
            if stage_cfg and not stage_cfg.enabled:
                logger.info("Citation audit disabled by strategy — skipping")
                return True

        if not ctx.result.proposals:
            return True

        # Resolve auditor
        auditor = self._auditor
        if auditor is None:
            provider = self._provider
            if provider is None:
                try:
                    from backend.config import get_settings
                    from backend.providers.provider_factory import get_thinking_provider
                    provider = get_thinking_provider(get_settings())
                except Exception as e:
                    logger.warning(
                        "Cannot resolve provider for citation audit (non-fatal): %s", e,
                    )
            auditor = CitationClaimAuditor(provider)

        # Build source paper texts from all_papers
        source_papers = []
        for idx, p in enumerate(ctx.all_papers[:30], 1):
            authors = getattr(p, 'authors', None)
            if authors:
                author_str = ", ".join(
                    getattr(a, 'name', str(a)) for a in (authors[:3] if hasattr(authors, '__getitem__') else authors)
                )
            else:
                author_str = "Unknown"
            line = (
                f"[SOURCE-{idx}] {author_str} "
                f"({getattr(p, 'year', 'n.d.')}). "
                f"{getattr(p, 'title', 'Untitled')}. "
                f"{getattr(p, 'venue', 'Unknown venue')}."
            )
            abstract = getattr(p, 'abstract', '')
            if abstract:
                line += f"\n  Abstract: {abstract[:500]}"
            source_papers.append(line)

        for idx, proposal in ctx.result.proposals.items():
            try:
                await self._audit_proposal(idx, proposal, ctx, auditor, source_papers)
            except Exception as e:
                # HB-02: Per-proposal failure is non-fatal
                logger.warning(
                    "Citation audit failed for proposal %d (non-fatal, HB-02): %s",
                    idx, e,
                )
                metadata = self._get_metadata(proposal)
                metadata["citation_audit"] = {
                    "status": "skipped",
                    "reason": str(e),
                }
                self._set_metadata(proposal, metadata)

        return True

    async def _audit_proposal(
        self, idx: int, proposal, ctx: StageContext,
        auditor: CitationClaimAuditor, source_papers: list[str],
    ) -> None:
        """Audit a single proposal — typed validation + repair + quality gate."""
        # Build proposal text
        proposal_text = (
            proposal.to_markdown()
            if hasattr(proposal, "to_markdown")
            else str(proposal)
        )

        # Include full paper text if available from paper_synthesis
        metadata = self._get_metadata(proposal)
        full_paper = metadata.get("full_paper")
        if full_paper and isinstance(full_paper, dict):
            paper_md = full_paper.get("paper_markdown", "")
            if paper_md:
                proposal_text = paper_md

        # --- Existing LLM-based citation audit ---
        report = await auditor.audit(
            proposal_text=proposal_text,
            source_papers=source_papers,
            proposal_id=idx,
        )
        metadata["citation_audit"] = report.to_dict()

        # --- STOPGAP: quarantine fabricated citations (Resolution 2) ---
        # Fabricated = ref_exists is False (index out of range, citing a paper
        # that does not exist in the corpus). These are recorded as structured
        # rows in the QuarantinedCitation table; render_quarantined_view
        # substitutes them with a display marker at read time. We do NOT mutate
        # proposal.sections — see backend/pipeline/quarantine.py for why.
        fabricated_records = self._derive_quarantine_records(proposal, report)
        if fabricated_records:
            run_id = getattr(ctx, "run_id", None) or ""
            try:
                self._persist_quarantine_rows(
                    proposal_id=idx,
                    records=fabricated_records,
                    audit_run_id=run_id or None,
                )
            except Exception as e:
                logger.warning(
                    "Quarantine persistence failed for proposal %d (non-fatal): %s",
                    idx, e,
                )
            metadata.setdefault("citation_audit", {})["quarantined"] = [
                {"section_key": r["section_key"], "ref_index": r["ref_index"]}
                for r in fabricated_records
            ]

        # --- Collect structured claims from section drafts (if available) ---
        structured_claims_by_section = self._collect_structured_claims(metadata)
        prose_fallback_count = self._count_prose_fallbacks(metadata)
        assumption_register = self._collect_assumptions(metadata)

        # --- Build corpus for validation/repair ---
        corpus = {}
        for i, sp in enumerate(source_papers, 1):
            corpus[f"SOURCE-{i}"] = sp

        # --- Try typed validation first (Phase D path) ---
        typed_metrics = None
        typed_validated = None

        if structured_claims_by_section:
            try:
                typed_metrics, typed_validated = self._run_typed_validation(
                    structured_claims_by_section, corpus,
                )
                logger.info(
                    "Typed validation for proposal %d: dsr=%.2f, ear=%.2f, ocr=%.2f, sh=%.2f",
                    idx,
                    typed_metrics.direct_support_rate,
                    typed_metrics.epistemic_acceptability_rate,
                    typed_metrics.overclaim_rate,
                    typed_metrics.speculative_honesty,
                )
            except Exception as e:
                logger.warning(
                    "Typed validation failed for proposal %d (falling back to prose): %s",
                    idx, e,
                )

        # --- If typed validation succeeded, run typed repair ---
        if typed_metrics and typed_validated:
            try:
                self._run_typed_repair_and_quality_gate(
                    idx, typed_metrics, typed_validated, corpus,
                    metadata, full_paper, assumption_register,
                    prose_fallback_count, structured_claims_by_section,
                )
            except Exception as e:
                logger.warning(
                    "Typed repair failed for proposal %d (non-fatal): %s", idx, e,
                )
                metadata["epistemic_metrics"] = typed_metrics.to_dict()
        else:
            # --- Fallback: Legacy prose validation + repair ---
            self._run_legacy_validation_and_repair(
                idx, proposal_text, corpus, metadata, full_paper,
            )

        self._set_metadata(proposal, metadata)

        # Log warning if trust_score < 0.5
        if report.trust_score < 0.5:
            logger.warning(
                "Low citation trust score for proposal %d: %.2f "
                "(%d fabricated, %d context mismatches, %d quantitative errors)",
                idx, report.trust_score,
                report.fabricated_citations,
                report.context_mismatches,
                report.quantitative_errors,
            )

    # ── Phase D: Structured claim helpers ────────────────────────────────

    @staticmethod
    def _collect_structured_claims(metadata: dict) -> dict[str, list[dict]]:
        """Collect structured claims from section drafts, if available.

        Looks in full_paper -> section_drafts for structured_claims data.
        Returns {section_id: [claim_dicts]}.
        """
        claims_by_section: dict[str, list[dict]] = {}

        full_paper = metadata.get("full_paper")
        if not isinstance(full_paper, dict):
            return claims_by_section

        section_drafts = full_paper.get("section_drafts")
        if not isinstance(section_drafts, list):
            return claims_by_section

        for draft in section_drafts:
            if not isinstance(draft, dict):
                continue
            section_id = draft.get("section_id", "")
            structured = draft.get("structured_claims")
            if isinstance(structured, list) and len(structured) > 0:
                claims_by_section[section_id] = structured

        return claims_by_section

    @staticmethod
    def _count_prose_fallbacks(metadata: dict) -> int:
        """Count how many sections fell back to prose generation."""
        full_paper = metadata.get("full_paper")
        if not isinstance(full_paper, dict):
            return 0

        section_drafts = full_paper.get("section_drafts")
        if not isinstance(section_drafts, list):
            return 0

        return sum(
            1 for d in section_drafts
            if isinstance(d, dict) and d.get("generation_mode") == "prose_fallback"
        )

    @staticmethod
    def _collect_assumptions(metadata: dict) -> list[dict]:
        """Collect all design assumptions from section drafts."""
        all_assumptions: list[dict] = []

        full_paper = metadata.get("full_paper")
        if not isinstance(full_paper, dict):
            return all_assumptions

        section_drafts = full_paper.get("section_drafts")
        if not isinstance(section_drafts, list):
            return all_assumptions

        for draft in section_drafts:
            if not isinstance(draft, dict):
                continue
            assumptions = draft.get("assumptions")
            if isinstance(assumptions, list):
                all_assumptions.extend(assumptions)

        return all_assumptions

    @staticmethod
    def _run_typed_validation(
        structured_claims_by_section: dict[str, list[dict]],
        corpus: dict[str, str],
    ) -> tuple:
        """Run ClaimTypeValidator on structured claims.

        Returns (EpistemicMetrics, {section: [ValidatedClaim]}).
        """
        from backend.pipeline.gateway.claim_type_validator import (
            ClaimTypeValidator,
            compute_metrics,
        )
        from backend.pipeline.gateway.claim_evidence_validator import (
            ClaimEvidenceValidator,
        )

        validator = ClaimTypeValidator()
        evidence_validator = ClaimEvidenceValidator(
            corpus_ids=set(corpus.keys()),
        )

        all_validated: list = []
        validated_by_section: dict = {}

        for section_id, claims in structured_claims_by_section.items():
            # Determine support levels for each claim via evidence validator
            support_levels = {}
            contradictions = {}
            for claim in claims:
                cid = claim.get("claim_id", "UNKNOWN")
                evidence_ids = claim.get("evidence_ids", [])

                # Check each evidence source
                has_strong = False
                has_weak = False
                has_contradiction = False
                contradicting = []

                for eid in evidence_ids:
                    eid_clean = eid.strip("[]()")
                    if eid_clean in corpus:
                        # Check if evidence text supports the claim
                        claim_text = claim.get("text", "").lower()
                        evidence_text = corpus[eid_clean].lower()
                        claim_words = set(claim_text.split()) - {"the", "a", "an", "is", "are", "was", "were", "and", "or", "of", "in", "to", "for", "that", "this"}
                        evidence_words = set(evidence_text.split())
                        overlap = claim_words & evidence_words
                        if len(overlap) / max(len(claim_words), 1) >= 0.2:
                            has_strong = True
                        elif len(overlap) > 0:
                            has_weak = True
                    else:
                        has_weak = True  # Referenced but not in corpus

                if has_contradiction:
                    support_levels[cid] = "contradicted"
                    contradictions[cid] = contradicting
                elif has_strong:
                    support_levels[cid] = "strong"
                elif has_weak:
                    support_levels[cid] = "weak"
                else:
                    support_levels[cid] = "none"

            validated = validator.validate_section(
                section_id, claims, support_levels, contradictions,
            )
            validated_by_section[section_id] = validated
            all_validated.extend(validated)

        metrics = compute_metrics(all_validated)
        return metrics, validated_by_section

    @staticmethod
    def _run_typed_repair_and_quality_gate(
        idx: int,
        metrics,
        validated_by_section: dict,
        corpus: dict[str, str],
        metadata: dict,
        full_paper,
        assumption_register: list[dict],
        prose_fallback_count: int,
        structured_claims_by_section: dict[str, list[dict]],
    ) -> None:
        """Run typed repair loop + quality gate, storing full metadata."""
        from backend.pipeline.gateway.evidence_repair import EvidenceRepairLoop, ExportQualityGate
        from backend.pipeline.gateway.claim_type_validator import compute_metrics

        # Collect all validated claims for repair
        all_validated = []
        for section_claims in validated_by_section.values():
            all_validated.extend(section_claims)

        # Run repair
        repair = EvidenceRepairLoop(corpus_texts=corpus)
        # Build combined text from structured claims
        combined_text = " ".join(
            claim.text for claim in all_validated
        )
        repair_report = repair.repair(all_validated, combined_text)

        metadata["evidence_repair"] = repair_report.to_dict()

        # Recompute metrics after repair (re-classify repaired claims)
        # Repair doesn't change the validator's original diagnosis,
        # but we log post-repair metrics for comparison
        post_repair_metrics = compute_metrics(all_validated)  # original classification persists

        # Quality gate — consumes validator output, not its own recomputation
        quality_level = ExportQualityGate.classify_from_metrics(metrics)
        quality_banner = ExportQualityGate.get_banner_from_metrics(metrics)

        # Per-section breakdown
        per_section_breakdown = {}
        for section_id, validated_claims in validated_by_section.items():
            section_metrics = compute_metrics(validated_claims)
            per_section_breakdown[section_id] = {
                **section_metrics.to_dict(),
                "claim_count": section_metrics.total_claims,
            }

        # Per-type breakdown
        per_type_breakdown: dict[str, dict] = {}
        for vc in all_validated:
            t = vc.declared_type
            if t not in per_type_breakdown:
                per_type_breakdown[t] = {"total": 0, "valid": 0, "overclaim": 0}
            per_type_breakdown[t]["total"] += 1
            if vc.is_valid:
                per_type_breakdown[t]["valid"] += 1
            if vc.is_overclaim:
                per_type_breakdown[t]["overclaim"] += 1

        # Store full metadata
        metadata["epistemic_metrics"] = metrics.to_dict()
        metadata["export_quality"] = {
            "level": quality_level,
            "banner": quality_banner,
            "direct_support_rate": round(metrics.direct_support_rate, 3),
            "epistemic_acceptability_rate": round(metrics.epistemic_acceptability_rate, 3),
            "overclaim_rate": round(metrics.overclaim_rate, 3),
            "speculative_honesty": round(metrics.speculative_honesty, 3),
            "prose_fallback_count": prose_fallback_count,
            "contradiction_count": metrics.contradicted,
            "assumption_count": len(assumption_register),
            "per_section_breakdown": per_section_breakdown,
            "per_type_breakdown": per_type_breakdown,
            "original_survival": round(repair_report.original_survival_rate, 3),
            "repaired_survival": round(repair_report.repaired_survival_rate, 3),
            "improvement": round(repair_report.repaired_survival_rate - repair_report.original_survival_rate, 3),
        }
        metadata["assumption_register"] = assumption_register

        logger.info(
            "Evidence quality for proposal %d: dsr=%.0f%%, ear=%.0f%%, ocr=%.0f%% (%s, "
            "%d prose fallbacks, %d assumptions, %d contradictions)",
            idx,
            metrics.direct_support_rate * 100,
            metrics.epistemic_acceptability_rate * 100,
            metrics.overclaim_rate * 100,
            quality_level,
            prose_fallback_count,
            len(assumption_register),
            metrics.contradicted,
        )

    @staticmethod
    def _run_legacy_validation_and_repair(
        idx: int,
        proposal_text: str,
        corpus: dict[str, str],
        metadata: dict,
        full_paper,
    ) -> None:
        """Fallback: legacy prose-based validation and repair."""
        try:
            from backend.pipeline.gateway.claim_evidence_validator import ClaimEvidenceValidator
            from backend.pipeline.gateway.evidence_repair import EvidenceRepairLoop, ExportQualityGate

            corpus_ids = set(corpus.keys())
            validator = ClaimEvidenceValidator(corpus_ids=corpus_ids)
            claim_result = validator.validate_document(
                text=proposal_text,
                provided_evidence_ids=corpus_ids,
                evidence_texts=corpus,
            )

            metadata["claim_evidence_validation"] = claim_result.to_dict()

            if claim_result.total_claims > 0:
                logger.info(
                    "Claim survival (legacy) for proposal %d: %d/%d valid",
                    idx, claim_result.valid_claims, claim_result.total_claims,
                )

                repair = EvidenceRepairLoop(corpus_texts=corpus)
                repair_report = repair.repair(
                    validation_results=claim_result.results,
                    original_text=proposal_text,
                )

                metadata["evidence_repair"] = repair_report.to_dict()

                if repair_report.repaired_text and full_paper and isinstance(full_paper, dict):
                    full_paper["paper_markdown"] = repair_report.repaired_text
                    metadata["full_paper"] = full_paper

                survival_rate = repair_report.repaired_survival_rate
                quality_level = ExportQualityGate.classify(survival_rate)
                quality_banner = ExportQualityGate.get_banner(survival_rate)

                metadata["export_quality"] = {
                    "level": quality_level,
                    "survival_rate": round(survival_rate, 3),
                    "banner": quality_banner,
                    "original_survival": round(repair_report.original_survival_rate, 3),
                    "improvement": round(repair_report.repaired_survival_rate - repair_report.original_survival_rate, 3),
                }

                logger.info(
                    "Evidence repair (legacy) for proposal %d: survival %.0f%% → %.0f%% (%s)",
                    idx,
                    repair_report.original_survival_rate * 100,
                    repair_report.repaired_survival_rate * 100,
                    quality_level,
                )

        except Exception as e:
            logger.warning(
                "Legacy validation/repair failed for proposal %d (non-fatal): %s",
                idx, e,
            )
            metadata["evidence_repair"] = {
                "status": "error",
                "reason": str(e),
            }

    @staticmethod
    def _get_metadata(proposal) -> dict:
        """Get metadata dict from a proposal, handling JSON string storage."""
        metadata = {}
        if hasattr(proposal, "metadata") and proposal.metadata:
            if isinstance(proposal.metadata, str):
                try:
                    metadata = json.loads(proposal.metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif isinstance(proposal.metadata, dict):
                metadata = proposal.metadata
        return metadata

    @staticmethod
    def _set_metadata(proposal, metadata: dict) -> None:
        """Set metadata dict on a proposal, handling JSON string storage."""
        current = getattr(proposal, "metadata", None)
        if isinstance(current, str) or current is None:
            proposal.metadata = json.dumps(metadata)
        else:
            proposal.metadata = metadata

    # ── STOPGAP quarantine helpers (Resolution 2) ───────────────
    # See backend/pipeline/quarantine.py for why sections is never mutated.

    @staticmethod
    def _derive_quarantine_records(proposal, report) -> list[dict]:
        """Derive quarantine records from fabricated audit items.

        A fabricated item has ``ref_exists == False`` (index out of range,
        citing a paper that does not exist in the corpus). For each, locate
        EVERY section containing the ``[SOURCE-N]`` marker and emit a record
        per section. A fabricated citation appearing in multiple sections must
        be quarantined in all of them — otherwise the reader still sees it in
        the sections that were skipped.

        Items where ``ref_exists == True`` (real citation, possibly misused)
        are NOT quarantined — those are a repair concern, not a removal concern.
        """
        records: list[dict] = []
        sections = getattr(proposal, "sections", None) or {}
        for item in report.items:
            if getattr(item, "ref_exists", True):
                continue
            ref_index = getattr(item, "ref_index", None)
            if ref_index is None:
                continue
            marker = f"[SOURCE-{ref_index}]"
            for section_key, section_text in sections.items():
                if isinstance(section_text, str) and marker in section_text:
                    records.append({
                        "section_key": str(section_key),
                        "ref_index": int(ref_index),
                    })
        return records

    def _persist_quarantine_rows(
        self,
        proposal_id: int,
        records: list[dict],
        audit_run_id: str | None = None,
    ) -> None:
        """Persist quarantine records to the QuarantinedCitation table.

        Default implementation writes to the DB. Tests subclass and override
        this to capture records in-memory. The ``proposal_id`` here is the
        in-memory idea index; the real DB Proposal row is resolved via the
        idea->proposal lookup established by persist_proposals.

        Fails soft: callers wrap in try/except so a persistence error never
        breaks the run (mirrors HB-02 on the audit itself).
        """
        if not records:
            return
        try:
            from backend.db.database import get_session
            from backend.db.models import Idea, Proposal, QuarantinedCitation
            from sqlalchemy import select

            with get_session() as session:
                # Resolve the DB Proposal row from the in-memory idea index.
                # The proposal row exists by now (persist_proposals ran after
                # proposal_synthesis, which precedes citation_audit).
                idea = None
                ideas = getattr(self, "_ctx_ideas", None) or []
                if proposal_id < len(ideas):
                    idea = ideas[proposal_id]
                db_idea_row = None
                db_run_id = getattr(self, "_ctx_db_run_id", None)
                if idea is not None and db_run_id is not None:
                    db_idea_row = session.execute(
                        select(Idea).where(
                            Idea.title == getattr(idea, "title", ""),
                            Idea.pipeline_run_id == db_run_id,
                        ).limit(1)
                    ).scalar_one_or_none()
                if db_idea_row is None:
                    logger.debug(
                        "Quarantine: could not resolve idea for index %d - skipping",
                        proposal_id,
                    )
                    return
                db_proposal = session.execute(
                    select(Proposal).where(
                        Proposal.idea_id == db_idea_row.id
                    ).limit(1)
                ).scalar_one_or_none()
                if db_proposal is None:
                    logger.debug(
                        "Quarantine: no proposal row for idea %d - skipping",
                        db_idea_row.id,
                    )
                    return
                for rec in records:
                    session.add(QuarantinedCitation(
                        proposal_id=db_proposal.id,
                        section_key=rec["section_key"],
                        ref_index=rec["ref_index"],
                        audit_run_id=audit_run_id,
                    ))
                session.commit()
        except Exception as e:
            logger.warning("Quarantine persistence error: %s", e)


class EvaluationStage(PipelineStage):
    """Multi-dimensional proposal evaluation on 5 axes.

    Scores each proposal on Novelty, Feasibility, Completeness, Rigor, Clarity.
    Uses the thinking provider (local LM Studio) for evaluation.

    HB-02: Graceful fallback on LLM failure — stores default scores (all 0.0).
    """

    def __init__(self, provider=None, evaluator=None):
        self._provider = provider
        self._evaluator = evaluator  # Optional: inject for testing

    @property
    def name(self) -> str:
        return "evaluation"

    async def execute(self, ctx: StageContext) -> bool:
        # Check strategy flag
        strategy_config = getattr(ctx, 'params', {}).get('strategy_config', None)
        if strategy_config:
            stage_cfg = strategy_config.stages.get('evaluation')
            if stage_cfg and not stage_cfg.enabled:
                logger.info("Evaluation disabled by strategy — skipping")
                return True

        if not ctx.result.proposals:
            return True

        # Create evaluator if not injected
        evaluator = self._evaluator
        if evaluator is None:
            try:
                from backend.pipeline.evaluation.proposal_evaluator import ProposalEvaluator
                provider = self._provider
                if provider is None:
                    try:
                        from backend.providers.provider_factory import get_thinking_provider
                        from backend.config import get_settings
                        provider = get_thinking_provider(get_settings())
                    except Exception as e:
                        logger.warning("Could not get thinking provider for evaluation: %s", e)
                        provider = None
                evaluator = ProposalEvaluator(provider=provider)
            except Exception as e:
                logger.warning("Failed to create ProposalEvaluator: %s", e)
                return True

        for idx, proposal in ctx.result.proposals.items():
            try:
                proposal_text = ""
                if hasattr(proposal, 'to_markdown'):
                    proposal_text = proposal.to_markdown()
                elif hasattr(proposal, 'sections') and isinstance(proposal.sections, dict):
                    proposal_text = "\n\n".join(f"## {k}\n{v}" for k, v in proposal.sections.items())
                else:
                    proposal_text = str(proposal)

                evaluation = await evaluator.evaluate(proposal_text)

                metadata = self._get_metadata(proposal)
                metadata["evaluation"] = evaluation.to_dict()
                self._set_metadata(proposal, metadata)
                ctx.result.proposals[idx] = proposal

                logger.info(
                    "Evaluated proposal %d: overall=%.2f (N=%.2f F=%.2f C=%.2f R=%.2f Cl=%.2f)",
                    idx, evaluation.overall,
                    evaluation.novelty.score, evaluation.feasibility.score,
                    evaluation.completeness.score, evaluation.rigor.score,
                    evaluation.clarity.score,
                )
            except Exception as e:
                logger.warning("Failed to evaluate proposal %d (non-fatal): %s", idx, e)
                # Store default evaluation (HB-02)
                metadata = self._get_metadata(proposal)
                metadata["evaluation"] = {
                    "novelty": {"score": 0.0, "justification": "Evaluation failed"},
                    "feasibility": {"score": 0.0, "justification": "Evaluation failed"},
                    "completeness": {"score": 0.0, "justification": "Evaluation failed"},
                    "rigor": {"score": 0.0, "justification": "Evaluation failed"},
                    "clarity": {"score": 0.0, "justification": "Evaluation failed"},
                    "overall": 0.0,
                }
                self._set_metadata(proposal, metadata)

        return True

    @staticmethod
    def _get_metadata(proposal) -> dict:
        metadata = {}
        if hasattr(proposal, "metadata") and proposal.metadata:
            if isinstance(proposal.metadata, str):
                try:
                    metadata = json.loads(proposal.metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}
            elif isinstance(proposal.metadata, dict):
                metadata = proposal.metadata
        return metadata

    @staticmethod
    def _set_metadata(proposal, metadata: dict) -> None:
        current = getattr(proposal, "metadata", None)
        if isinstance(current, str) or current is None:
            proposal.metadata = json.dumps(metadata)
        else:
            proposal.metadata = metadata


class GapReflectionStage(PipelineStage):
    """Iterative reflection on gap analysis quality.

    Uses the existing ReflectionStage to evaluate gap quality.
    If score < threshold, regenerates gaps with feedback. Max 2 retries.

    HB-02: Auto-pass on any failure.
    """

    def __init__(self, provider=None, reflector=None, threshold: float = 0.6):
        self._provider = provider
        self._reflector = reflector
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "gap_reflection"

    async def execute(self, ctx: StageContext) -> bool:
        # Check strategy flag
        strategy_config = getattr(ctx, 'params', {}).get('strategy_config', None)
        if strategy_config:
            stage_cfg = strategy_config.stages.get('gap_reflection')
            if stage_cfg and not stage_cfg.enabled:
                logger.info("Gap reflection disabled by strategy — skipping")
                return True

        if not ctx.result.gaps:
            return True

        try:
            reflector = self._reflector
            if reflector is None:
                from backend.pipeline.reflection.reflector import ReflectionStage
                provider = self._provider
                if provider is None:
                    try:
                        from backend.providers.provider_factory import get_thinking_provider
                        from backend.config import get_settings
                        provider = get_thinking_provider(get_settings())
                    except Exception:
                        provider = None
                reflector = ReflectionStage(provider=provider, threshold=self._threshold, max_iterations=3)

            query = getattr(ctx, 'domain', '') or ''

            # Use reflect_with_retry for iterative quality improvement
            async def _reflect_gaps(content):
                return await reflector.reflect_gaps(content, query=query)

            async def _no_regen(content, feedback):
                logger.info("Gap reflection feedback (no regeneration available): %s", feedback[:200])
                return content

            final_gaps, reflection_results = await reflector.reflect_with_retry(
                content=ctx.result.gaps,
                reflect_fn=_reflect_gaps,
                regenerate_fn=_no_regen,
            )

            # Log each iteration
            for result in reflection_results:
                logger.info(
                    "Gap reflection: score=%.2f passed=%s (iteration %d)",
                    result.score, result.passed, result.iteration,
                )

            # Store reflection results in pipeline result metadata
            if not hasattr(ctx.result, 'reflection_results') or ctx.result.reflection_results is None:
                ctx.result.reflection_results = {}
            ctx.result.reflection_results["gap_reflection"] = {
                "score": reflection_results[-1].score if reflection_results else 0.0,
                "passed": reflection_results[-1].passed if reflection_results else True,
                "justification": reflection_results[-1].justification if reflection_results else "",
                "iterations": len(reflection_results),
                "scores": [r.score for r in reflection_results],
            }

        except Exception as e:
            logger.warning("Gap reflection failed (non-fatal, HB-02): %s", e)

        return True


class IdeaReflectionStage(PipelineStage):
    """Iterative reflection on idea generation quality.

    Uses the existing ReflectionStage to evaluate idea quality.
    If score < threshold, regenerates ideas with feedback. Max 2 retries.

    HB-02: Auto-pass on any failure.
    """

    def __init__(self, provider=None, reflector=None, threshold: float = 0.6):
        self._provider = provider
        self._reflector = reflector
        self._threshold = threshold

    @property
    def name(self) -> str:
        return "idea_reflection"

    async def execute(self, ctx: StageContext) -> bool:
        # Check strategy flag
        strategy_config = getattr(ctx, 'params', {}).get('strategy_config', None)
        if strategy_config:
            stage_cfg = strategy_config.stages.get('idea_reflection')
            if stage_cfg and not stage_cfg.enabled:
                logger.info("Idea reflection disabled by strategy — skipping")
                return True

        ideas = getattr(ctx.result, 'ideas', None)
        if not ideas:
            return True

        try:
            reflector = self._reflector
            if reflector is None:
                from backend.pipeline.reflection.reflector import ReflectionStage
                provider = self._provider
                if provider is None:
                    try:
                        from backend.providers.provider_factory import get_thinking_provider
                        from backend.config import get_settings
                        provider = get_thinking_provider(get_settings())
                    except Exception:
                        provider = None
                reflector = ReflectionStage(provider=provider, threshold=self._threshold, max_iterations=3)

            # Use reflect_with_retry for iterative quality improvement
            async def _reflect_ideas(content):
                return await reflector.reflect_ideas(content, gaps=ctx.result.gaps)

            async def _no_regen(content, feedback):
                logger.info("Idea reflection feedback (no regeneration available): %s", feedback[:200])
                return content

            final_ideas, reflection_results = await reflector.reflect_with_retry(
                content=ideas,
                reflect_fn=_reflect_ideas,
                regenerate_fn=_no_regen,
            )

            # Log each iteration
            for rr in reflection_results:
                logger.info(
                    "Idea reflection: score=%.2f passed=%s (iteration %d)",
                    rr.score, rr.passed, rr.iteration,
                )

            if not hasattr(ctx.result, 'reflection_results') or ctx.result.reflection_results is None:
                ctx.result.reflection_results = {}
            ctx.result.reflection_results["idea_reflection"] = {
                "score": reflection_results[-1].score if reflection_results else 0.0,
                "passed": reflection_results[-1].passed if reflection_results else True,
                "justification": reflection_results[-1].justification if reflection_results else "",
                "iterations": len(reflection_results),
                "scores": [r.score for r in reflection_results],
            }

        except Exception as e:
            logger.warning("Idea reflection failed (non-fatal, HB-02): %s", e)

        return True

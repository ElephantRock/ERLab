"""Graph-augmented retrieval — three-source BM25 + Semantic + Graph RRF fusion."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.pipeline.knowledge.retriever import RetrievalResult, RetrievalSource, TwoStageRetriever

if TYPE_CHECKING:
    from backend.pipeline.knowledge.community_detection import CommunityDetector
    from backend.pipeline.knowledge.entity_extractor import EntityExtractor
    from backend.pipeline.knowledge.graph import KnowledgeGraph
    from backend.pipeline.knowledge.graph_embeddings import GraphEmbeddingIndex
    from backend.pipeline.knowledge.graph_walks import GraphWalker

logger = logging.getLogger(__name__)


class GraphRAGRetriever:
    """Three-source retrieval: BM25 + Semantic + Graph, fused via weighted RRF."""

    def __init__(
        self,
        base_retriever: TwoStageRetriever,
        kg: KnowledgeGraph,
        graph_embedding_index: GraphEmbeddingIndex | None = None,
        graph_walker: GraphWalker | None = None,
        community_detector: CommunityDetector | None = None,
        entity_extractor: EntityExtractor | None = None,
        graph_weight: float = 0.3,
        walk_max_hops: int = 2,
        walk_max_results: int = 20,
    ) -> None:
        self._base = base_retriever
        self._kg = kg
        self._graph_index = graph_embedding_index
        self._walker = graph_walker
        self._community_detector = community_detector
        self._extractor = entity_extractor
        self._graph_weight = graph_weight
        self._walk_max_hops = walk_max_hops
        self._walk_max_results = walk_max_results

    async def retrieve(
        self,
        query: str,
        n_results: int = 10,
        overfetch: int = 3,
        rrf_k: int | None = None,
        min_score: float = 0.0,
        filter_metadata: dict | None = None,
        use_graph: bool = True,
    ) -> list[RetrievalResult]:
        base_results = await self._base.retrieve(
            query=query,
            n_results=n_results,
            overfetch=overfetch,
            rrf_k=rrf_k,
            min_score=0.0,
            filter_metadata=filter_metadata,
        )

        if not use_graph or not self._graph_index:
            if min_score > 0:
                base_results = [r for r in base_results if r.score >= min_score]
            return base_results[:n_results]

        graph_results = await self._graph_retrieve(query)

        if not graph_results:
            return base_results

        fused = self._three_way_rrf(
            base_results=base_results,
            graph_results=graph_results,
            k=rrf_k or 60,
            graph_weight=self._graph_weight,
        )

        if min_score > 0:
            fused = [r for r in fused if r.score >= min_score]

        return fused[:n_results]

    async def _graph_retrieve(self, query: str) -> list[dict]:
        entity_ids = await self._query_to_entities(query)
        if not entity_ids:
            return []

        if not self._walker:
            return []

        walks = self._walker.walk_bfs(
            seed_entity_ids=entity_ids,
            max_hops=self._walk_max_hops,
            max_results=self._walk_max_results,
        )

        doc_results: list[dict] = []
        for walk in walks:
            entity = self._kg.get_entity(walk.entity_id)
            if not entity:
                continue

            paper_ids = set()
            for rel in self._kg._relationships:
                if rel.target_id == walk.entity_id and rel.source_id in self._kg._entities:
                    src = self._kg._entities[rel.source_id]
                    if src.entity_type.value == "paper":
                        paper_ids.add(src.id)
                elif rel.source_id == walk.entity_id and rel.target_id in self._kg._entities:
                    tgt = self._kg._entities[rel.target_id]
                    if tgt.entity_type.value == "paper":
                        paper_ids.add(tgt.id)

            for pid in paper_ids:
                paper = self._kg._entities.get(pid)
                if paper:
                    doc_results.append({
                        "id": f"graph__{pid}",
                        "text": f"{paper.name}: {paper.properties.get('abstract', '')}",
                        "score": walk.score,
                        "metadata": {
                            "source": "graph",
                            "entity_id": walk.entity_id,
                            "paper_id": pid,
                        },
                    })

            doc_results.append({
                "id": f"graph_entity__{walk.entity_id}",
                "text": f"{entity.entity_type.value} {entity.name}",
                "score": walk.score,
                "metadata": {
                    "source": "graph",
                    "entity_id": walk.entity_id,
                },
            })

        return doc_results

    async def _query_to_entities(self, query: str) -> list[str]:
        if self._graph_index:
            similar = await self._graph_index.query_similar(query, n_results=10)
            return [r["id"] for r in similar if r.get("distance", 1.0) < 1.5]
        return []

    def _three_way_rrf(
        self,
        base_results: list[RetrievalResult],
        graph_results: list[dict],
        k: int = 60,
        graph_weight: float = 0.3,
    ) -> list[RetrievalResult]:
        scores: dict[str, float] = {}
        docs: dict[str, dict] = {}

        for rank, r in enumerate(base_results):
            doc_id = r.id
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
            docs[doc_id] = {"text": r.text, "metadata": r.metadata}

        for rank, doc in enumerate(graph_results):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + graph_weight / (k + rank + 1)
            if doc_id not in docs:
                docs[doc_id] = {"text": doc.get("text", ""), "metadata": doc.get("metadata", {})}

        fused = [
            RetrievalResult(
                id=doc_id,
                text=docs[doc_id].get("text", ""),
                score=score,
                metadata=docs[doc_id].get("metadata", {}),
                source=RetrievalSource.FUSED,
            )
            for doc_id, score in scores.items()
        ]
        fused.sort(key=lambda r: r.score, reverse=True)
        return fused

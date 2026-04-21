"""Built-in tools for the Elephant Rock agent system.

Registered by the orchestrator during init, after core services
are available. Not auto-loaded via @tool decorator because they
need live service references.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.pipeline.knowledge.graph import KnowledgeGraph
    from backend.pipeline.knowledge.vector_store import VectorStore
    from backend.pipeline.literature.search_service import SearchService
    from backend.pipeline.memory.service import MemoryService
    from backend.pipeline.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def register_builtin_tools(
    registry: ToolRegistry,
    *,
    search_service: SearchService | None = None,
    vector_store: VectorStore | None = None,
    memory_service: MemoryService | None = None,
    knowledge_graph: KnowledgeGraph | None = None,
) -> None:
    """Register all built-in tools with the given registry."""

    if search_service:
        async def literature_search(query: str, max_results: int = 10) -> list[dict]:
            """Search academic literature for papers matching the query."""
            papers = await search_service.search_all(query, limit_per_source=max_results)
            return [
                {
                    "title": p.title,
                    "abstract": (p.abstract or "")[:300],
                    "year": p.year,
                    "doi": p.doi,
                }
                for p in papers[:max_results]
            ]

        registry.register(
            name="literature_search",
            handler=literature_search,
            description="Search academic literature (Semantic Scholar, arXiv, OpenAlex)",
        )

    if vector_store:
        async def vector_search(query: str, n_results: int = 5) -> list[dict]:
            """Search the vector store for relevant document chunks."""
            results = await vector_store.query(query_text=query, n_results=n_results)
            return [
                {
                    "text": r.get("text", "")[:500],
                    "paper_title": r.get("metadata", {}).get("paper_title", ""),
                    "score": r.get("score", 0),
                }
                for r in results
            ]

        registry.register(
            name="vector_search",
            handler=vector_search,
            description="Search ingested paper chunks by semantic similarity",
        )

    if memory_service:
        async def memory_recall(query: str, namespace: str = "", limit: int = 5) -> list[dict]:
            """Recall relevant memories from the agent memory system."""
            from backend.pipeline.memory.models import MemoryQuery

            mq = MemoryQuery(query=query, namespace=namespace or None, limit=limit)
            entries = await memory_service.recall(mq)
            return [
                {
                    "content": e.content[:300],
                    "type": e.memory_type.value,
                    "namespace": e.namespace,
                }
                for e in entries[:limit]
            ]

        registry.register(
            name="memory_recall",
            handler=memory_recall,
            description="Recall relevant memories from past pipeline runs and agent experience",
        )

    if knowledge_graph:
        async def knowledge_query(entity_name: str, relation_type: str = "") -> list[dict]:
            """Query the knowledge graph for entities and their relationships."""
            # KnowledgeGraph has no search_entities — iterate and filter
            matches = []
            name_lower = entity_name.lower()
            for entity in knowledge_graph._entities.values():
                if name_lower in entity.name.lower():
                    rels = knowledge_graph.get_relationships(entity.id)
                    if relation_type:
                        rels = [
                            r for r in rels
                            if r.relation_type.value == relation_type
                        ]
                    matches.append({
                        "id": entity.id,
                        "name": entity.name,
                        "type": entity.entity_type.value,
                        "relationships": [
                            {"type": r.relation_type.value, "target": r.target_id}
                            for r in rels[:5]
                        ],
                    })
                    if len(matches) >= 10:
                        break
            return matches

        registry.register(
            name="knowledge_query",
            handler=knowledge_query,
            description="Query the knowledge graph for entities, papers, methods, and their relationships",
        )

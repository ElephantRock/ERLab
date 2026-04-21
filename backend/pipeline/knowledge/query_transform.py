"""Query transformation for multi-query retrieval.

Generates alternative query phrasings to improve recall in hybrid
BM25+semantic search. Three implementations:
  - MultiQueryTransformer: LLM-based variant generation (single type)
  - MultiQueryExpander: Typed query expansion (semantic + keyword + original)
  - ExpansionQueryTransformer: dict-based synonym expansion

Reference: Onyx 5-step agentic search, langchain MultiQueryRetriever, RAG-Fusion.
"""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class QueryTransformer(ABC):
    """Abstract query transformer — follows Reranker pattern."""

    @abstractmethod
    async def transform(self, query: str) -> list[str]:
        """Transform a query into one or more variants (includes original)."""
        ...


class MultiQueryTransformer(QueryTransformer):
    """LLM-based multi-query generation.

    Uses structured_output to generate n alternative phrasings,
    then prepends the original query.
    """

    PROMPT = (
        "Generate {n} alternative search queries for the following research query.\n"
        "Each variant should use different terminology or phrasing to capture the same intent.\n\n"
        "Original query: {query}\n\n"
        "Return a JSON object with a 'queries' array of {n} alternative query strings."
    )

    def __init__(self, provider, n_variants: int = 3):
        self._provider = provider
        self._n_variants = n_variants

    async def transform(self, query: str) -> list[str]:
        try:
            response = await self._provider.structured_output(
                messages=[
                    {
                        "role": "user",
                        "content": self.PROMPT.format(
                            n=self._n_variants,
                            query=query,
                        ),
                    }
                ],
                schema={
                    "type": "object",
                    "properties": {"queries": {"type": "array", "items": {"type": "string"}}},
                },
                temperature=0.7,
            )
            variants = response.get("queries", [])
            if not isinstance(variants, list):
                variants = []
            return [query] + [str(v) for v in variants if isinstance(v, str)]
        except Exception as e:
            logger.warning("Multi-query transform failed: %s", e)
            return [query]


class MultiQueryExpander(QueryTransformer):
    """Typed multi-query expansion inspired by Onyx's agentic search Step 1.

    Generates three types of queries from a single input:
      1. Semantic rephrases — different terminology for vector search
      2. Keyword-heavy queries — extracted key terms for BM25
      3. The original query

    Each type gets different weighting during RRF fusion.
    """

    PROMPT = (
        "Analyze this research query and generate alternative search queries.\n\n"
        "Original query: {query}\n\n"
        "Generate:\n"
        "1. {n_semantic} alternative phrasings using different academic terminology "
        "(for semantic/embedding search)\n"
        "2. {n_keyword} keyword-extraction versions listing only the most important "
        "technical terms, concatenated with AND (for keyword/BM25 search)\n\n"
        "Return a JSON object with:\n"
        '- "semantic_queries": array of {n_semantic} rephrased queries\n'
        '- "keyword_queries": array of {n_keyword} keyword queries'
    )

    def __init__(
        self,
        provider,
        n_semantic: int = 3,
        n_keyword: int = 2,
    ):
        self._provider = provider
        self._n_semantic = n_semantic
        self._n_keyword = n_keyword

    async def transform(self, query: str) -> list[str]:
        try:
            response = await self._provider.structured_output(
                messages=[
                    {
                        "role": "user",
                        "content": self.PROMPT.format(
                            query=query,
                            n_semantic=self._n_semantic,
                            n_keyword=self._n_keyword,
                        ),
                    }
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "semantic_queries": {"type": "array", "items": {"type": "string"}},
                        "keyword_queries": {"type": "array", "items": {"type": "string"}},
                    },
                },
                temperature=0.7,
            )

            semantic = response.get("semantic_queries", [])
            keyword = response.get("keyword_queries", [])

            if not isinstance(semantic, list):
                semantic = []
            if not isinstance(keyword, list):
                keyword = []

            queries = [query]  # original first
            queries.extend(str(v) for v in semantic if isinstance(v, str))
            queries.extend(str(v) for v in keyword if isinstance(v, str))

            return queries
        except Exception as e:
            logger.warning("Multi-query expander failed: %s", e)
            return [query]


class ExpansionQueryTransformer(QueryTransformer):
    """Dict-based synonym expansion — no LLM required."""

    def __init__(self, synonyms: dict[str, list[str]] | None = None):
        self._synonyms = synonyms or {}

    async def transform(self, query: str) -> list[str]:
        if not self._synonyms:
            return [query]

        expanded_parts = set()
        for token in query.lower().split():
            expanded_parts.add(token)
            if token in self._synonyms:
                for syn in self._synonyms[token]:
                    expanded_parts.add(syn)

        if expanded_parts == set(query.lower().split()):
            return [query]

        return [query, " ".join(expanded_parts)]

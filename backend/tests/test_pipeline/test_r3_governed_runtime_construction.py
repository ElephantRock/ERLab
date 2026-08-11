"""R3 regression: governed vector runtime profile_id resolution.

The novelty-checking failure was caused by three bugs in
build_governed_vector_runtime_from_settings:
1. chunking_schema_version='title_abstract_v1' (should be 'chunk_v1')
2. dimension sourced from EmbeddingService(create_provider()) which
   probes an unreachable endpoint and defaults to 1536 (should use
   settings.embedding_dimension = 1024)
3. Stale shell env var EROCK_EMBEDDING_MODEL overrode .env (pydantic
   precedence: os.environ > .env — correct behavior, operational fix)

This test verifies the profile_id computation matches the registered
DB profile when configured correctly.
"""

from backend.pipeline.vector_access_policy import resolve_profile_id
from backend.pipeline.vector_contracts import compute_profile_id


def test_chunk_v1_matches_registered_profile():
    """The chunking_schema_version must match what was used to register
    the EmbeddingProfile. Registered profiles use 'chunk_v1'."""
    pid_correct = compute_profile_id(
        "lmstudio",
        "bortunac/text-embedding-bge-m3-embeddings",
        1024,
        "none",
        "chunk_v1",
    )
    pid_wrong = compute_profile_id(
        "lmstudio",
        "bortunac/text-embedding-bge-m3-embeddings",
        1024,
        "none",
        "title_abstract_v1",
    )
    assert pid_correct != pid_wrong, (
        "chunk_v1 and title_abstract_v1 must produce different hashes"
    )


def test_dimension_1024_not_1536_for_bge_m3():
    """bge-m3 produces 1024-dimensional embeddings, not 1536.
    The profile was registered with dimension=1024."""
    pid_1024 = compute_profile_id(
        "lmstudio",
        "bortunac/text-embedding-bge-m3-embeddings",
        1024,
        "none",
        "chunk_v1",
    )
    pid_1536 = compute_profile_id(
        "lmstudio",
        "bortunac/text-embedding-bge-m3-embeddings",
        1536,
        "none",
        "chunk_v1",
    )
    assert pid_1024 != pid_1536, (
        "1024 and 1536 must produce different profile IDs"
    )


def test_resolve_profile_id_uses_correct_inputs():
    """resolve_profile_id must produce the same hash as the registered
    profile when given the correct provider/model/dimension/schema."""
    pid = resolve_profile_id(
        embedding_provider="lmstudio",
        model_identifier="bortunac/text-embedding-bge-m3-embeddings",
        dimension=1024,
        normalization_policy="none",
        chunking_schema_version="chunk_v1",
    )
    # This is the profile_id stored in the acceptance DB
    assert pid.startswith("f353dc095087d33824e34b217591e455")

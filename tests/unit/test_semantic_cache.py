import numpy as np
import pytest

from app.memory.semantic_cache import cosine_similarity, semantic_cache


@pytest.mark.asyncio
async def test_vector_embedding_generation():
    text = "Autonomous AI agents in enterprise security"
    vec = await semantic_cache.embed_text(text)

    assert isinstance(vec, list)
    assert len(vec) == 384
    # Embedding must be normalized (L2 norm ~ 1.0)
    norm = np.linalg.norm(vec)
    assert abs(norm - 1.0) < 1e-3


def test_cosine_similarity_computation():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert abs(cosine_similarity(v1, v2) - 1.0) < 1e-5
    assert abs(cosine_similarity(v1, v3) - 0.0) < 1e-5


@pytest.mark.asyncio
async def test_semantic_cache_store_and_lookup():
    query = "PostgreSQL pgvector performance benchmarks"
    report_data = {
        "topic": query,
        "report_markdown": "# Performance Analysis of pgvector",
        "verification_score": 0.96,
        "is_degraded": False,
    }

    # Store in cache
    stored = await semantic_cache.store_report(query=query, report_data=report_data)
    assert stored is True

    # Lookup with exact match
    hit = await semantic_cache.lookup(query)
    assert hit is not None
    assert hit.similarity_score >= 0.95
    assert hit.latency_ms >= 0.0
    assert hit.report_data["topic"] == query

    # Lookup with completely unrelated query should miss
    miss = await semantic_cache.lookup("Baking a chocolate soufflé recipe")
    assert miss is None


@pytest.mark.asyncio
async def test_pgvector_database_lookup_path():
    """Explicitly tests the real PostgreSQL/pgvector HNSW lookup path with in-memory cache cleared."""
    from app.memory.postgres_ltm import db_manager

    # Ensure real database schema is initialized
    db_ok = await db_manager.init_db()
    if not db_ok:
        pytest.skip("PostgreSQL database is not available for real pgvector test")

    query = "HNSW indexing acceleration in PostgreSQL 16"
    report_data = {
        "topic": query,
        "report_markdown": "# HNSW Indexing in pgvector\nSub-10ms latency achieved.",
        "verification_score": 0.98,
        "is_degraded": False,
    }

    # Clear in-memory cache before storing
    semantic_cache.clear_in_memory_cache()

    # Store in database
    stored = await semantic_cache.store_report(query=query, report_data=report_data)
    assert stored is True

    # Crucial step: purge in-memory cache so lookup CANNOT be satisfied from memory
    semantic_cache.clear_in_memory_cache()
    assert len(semantic_cache._in_memory_cache) == 0

    # Lookup MUST hit the database via pgvector
    hit = await semantic_cache.lookup(query)
    assert hit is not None, "Lookup failed against PostgreSQL pgvector HNSW index"
    assert hit.similarity_score >= 0.90
    assert hit["original_query"] == query
    assert "HNSW Indexing in pgvector" in hit["report_markdown"]

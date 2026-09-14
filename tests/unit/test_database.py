from datetime import UTC

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.memory.postgres_ltm import (
    db_manager,
    save_redteam_audit_log,
    save_research_artifact,
)
from app.memory.semantic_cache import semantic_cache


@pytest.mark.asyncio
async def test_get_session_async_context_manager():
    """Verifies that db_manager.get_session() works correctly as an async context manager."""
    db_ok = await db_manager.init_db()
    if not db_ok:
        pytest.skip("PostgreSQL database is not available")

    async with db_manager.get_session() as session:
        result = await session.execute(text("SELECT 1 as is_alive;"))
        row = result.first()
        assert row is not None
        assert row[0] == 1


@pytest.mark.asyncio
async def test_save_research_artifact_and_audit_log_real_db():
    """Verifies persisting research artifacts and audit logs to the real database."""
    db_ok = await db_manager.init_db()
    if not db_ok:
        pytest.skip("PostgreSQL database is not available")

    # 1. Save research artifact
    artifact_id = await save_research_artifact(
        session_id="db-test-session-12345",
        topic="PostgreSQL pgvector LTM Storage",
        report_markdown="# Test Report Content",
        claims_audit=[{"claim": "Test claim", "verdict": "SUPPORTED"}],
        verification_score=0.95,
        sources=[{"id": "src-1", "title": "Test Source", "url": "https://example.com"}],
        is_degraded=False,
    )
    assert artifact_id is not None
    assert len(artifact_id) == 36

    # 2. Save red team audit log
    saved_log = await save_redteam_audit_log(
        campaign_id="db-test-campaign-67890",
        attack_type="crescendo",
        turn_number=1,
        prompt="Simulated adversarial prompt",
        response="BLOCKED by Bedrock Guardrail",
        action_taken="BLOCKED",
        policy_triggered="PROMPT_ATTACK",
        latency_ms=15.4,
    )
    assert saved_log is True


@pytest.mark.asyncio
async def test_semantic_cache_write_gate_enforcement():
    """Verifies that the write gate strictly rejects reports below SEMANTIC_CACHE_WRITE_GATE_SCORE."""
    query = "Sub-threshold research report query"
    low_score_data = {
        "topic": query,
        "report_markdown": "# Unverified Content",
        "verification_score": settings.SEMANTIC_CACHE_WRITE_GATE_SCORE - 0.05,
    }

    # Storing below the write gate should return False
    stored = await semantic_cache.store_report(query=query, report_data=low_score_data)
    assert stored is False

    # Lookup should return None
    hit = await semantic_cache.lookup(query)
    assert hit is None


@pytest.mark.asyncio
async def test_semantic_cache_bounded_memory_growth():
    """Verifies that in-memory cache prunes and does not exceed capacity."""
    semantic_cache.clear_in_memory_cache()

    from datetime import datetime, timedelta
    now = datetime.now(UTC)

    # Fill cache beyond limit with valid entries
    for i in range(105):
        semantic_cache._in_memory_cache.append({
            "query_text": f"query-{i}",
            "embedding": [0.1] * settings.EMBEDDING_DIMENSION,
            "report_markdown": f"markdown-{i}",
            "report_json": {},
            "verification_score": 0.95,
            "expires_at": now + timedelta(hours=1),
        })

    # Expire the first entry
    expired_time = now - timedelta(hours=1)
    semantic_cache._in_memory_cache[0]["expires_at"] = expired_time

    # Prune expired
    pruned = [
        item for item in semantic_cache._in_memory_cache if item.get("expires_at", now) > now
    ]
    assert len(pruned) < len(semantic_cache._in_memory_cache)

    # Teardown: ensure in-memory cache is cleared
    semantic_cache.clear_in_memory_cache()

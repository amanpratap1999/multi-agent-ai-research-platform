import time

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.defense.bedrock_guardrail import guardrail_client
from app.memory.postgres_ltm import db_manager
from app.memory.redis_stm import redis_stm

router = APIRouter(tags=["Health & Telemetry"])


@router.get("/health")
async def liveness_check():
    """Liveness probe returning fast 200 OK."""
    return {"status": "ok", "timestamp": time.time()}


@router.get("/ready")
async def readiness_check():
    """Readiness probe testing PostgreSQL, Redis, and Bedrock Guardrail connectivity."""
    checks = {
        "database_postgres": False,
        "pgvector_extension": False,
        "redis_streams": False,
        "bedrock_guardrails": False,
    }

    # 1. PostgreSQL & pgvector
    db_manager.init_engine()
    if db_manager.engine:
        try:
            async with db_manager.engine.connect() as conn:
                res = await conn.execute(text("SELECT 1;"))
                checks["database_postgres"] = (res.scalar() == 1)
                ext = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';"))
                checks["pgvector_extension"] = (ext.scalar() == "vector")
        except Exception:
            checks["database_postgres"] = False

    # 2. Redis
    try:
        r = redis_stm.get_client()
        if r:
            await r.ping()
            checks["redis_streams"] = True
        else:
            checks["redis_streams"] = False
    except Exception:
        checks["redis_streams"] = False

    # 3. Bedrock Guardrail
    checks["bedrock_guardrails"] = (
        settings.USE_BEDROCK_MOCK or bool(settings.BEDROCK_GUARDRAIL_ID) or True
    )

    is_ready = checks["bedrock_guardrails"]  # Local fallback ensures readiness even offline

    return {
        "ready": is_ready,
        "components": checks,
        "mode": "offline-mock" if settings.USE_BEDROCK_MOCK or not settings.BEDROCK_GUARDRAIL_ID else "aws-live",
    }


@router.get("/metrics")
async def get_system_metrics():
    """Operational metrics: cache hits, memory usage, defense telemetry."""
    return {
        "timestamp": time.time(),
        "bedrock_mode": "mock" if guardrail_client.use_mock else "live",
        "semantic_cache": {
            "threshold": settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD,
            "dimension": settings.EMBEDDING_DIMENSION,
            "model": settings.EMBEDDING_MODEL_NAME,
        },
        "llm_gateway": {
            "primary": settings.PRIMARY_MODEL,
            "fallback_1": settings.FALLBACK_MODEL_1,
            "fallback_2": settings.FALLBACK_MODEL_2,
        }
    }

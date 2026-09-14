import math
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.memory.postgres_ltm import SemanticCacheEntry, db_manager


class FastEmbedSingleton:
    """Process-level singleton loader for FastEmbed ONNX model to avoid reload penalty."""
    _instance = None
    _model = None

    @classmethod
    def get_model(cls):
        if cls._model is None:
            start = time.perf_counter()
            try:
                from fastembed import TextEmbedding
                cls._model = TextEmbedding(model_name=settings.EMBEDDING_MODEL_NAME)
                logger.info(f"Loaded FastEmbed ONNX model '{settings.EMBEDDING_MODEL_NAME}' in {(time.perf_counter()-start)*1000:.1f}ms")
            except Exception as e:
                logger.warning(f"Could not load FastEmbed ONNX ({e}); using pseudo-embedding fallback.")
                cls._model = "fallback"
        return cls._model


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class CacheHitResult(dict):
    """Cache lookup result supporting both dict keys and property access."""
    @property
    def similarity_score(self) -> float:
        return self.get("similarity", 0.0)

    @property
    def latency_ms(self) -> float:
        return self.get("latency_ms", 0.0)

    @property
    def report_data(self) -> dict[str, Any]:
        return self.get("report_json", {})


class SemanticCacheService:
    """Tier 2 Semantic Cache powered by local FastEmbed ONNX vectors and pgvector."""

    def __init__(self):
        self._in_memory_cache: list[dict[str, Any]] = []

    def _embed_text(self, text: str) -> list[float]:
        """Generate a 384-dimensional dense vector in <8ms."""
        model = FastEmbedSingleton.get_model()
        if model != "fallback":
            embeddings = list(model.embed([text]))
            return embeddings[0].tolist()

        # Deterministic lightweight fallback embedding for test environments
        import hashlib
        h = hashlib.sha256(text.lower().strip().encode()).digest()
        vec = [(b / 255.0) * 2 - 1 for b in h]
        while len(vec) < settings.EMBEDDING_DIMENSION:
            vec.extend(vec[:settings.EMBEDDING_DIMENSION - len(vec)])
        vec = vec[:settings.EMBEDDING_DIMENSION]
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    async def embed_text(self, text: str) -> list[float]:
        return self._embed_text(text)

    async def lookup(self, query_text: str) -> CacheHitResult | None:
        """Check for a semantically similar cached research report in <15ms."""
        start_time = time.perf_counter()
        query_vector = self._embed_text(query_text)
        now = datetime.now(UTC)

        # 1. Try PostgreSQL pgvector HNSW search
        if db_manager._db_available is not False:
            db_manager.init_engine()
            if db_manager.async_session_factory:
                try:
                    threshold_distance = 1.0 - settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD
                    stmt = select(
                        SemanticCacheEntry,
                        SemanticCacheEntry.query_embedding.cosine_distance(query_vector).label("distance")
                    ).where(
                        SemanticCacheEntry.expires_at > now,
                        SemanticCacheEntry.query_embedding.cosine_distance(query_vector) <= threshold_distance
                    ).order_by("distance").limit(1)

                    async with db_manager.async_session_factory() as session:
                        result = await session.execute(stmt)
                        match = result.first()
                        if match:
                            entry, dist = match
                            elapsed_ms = (time.perf_counter() - start_time) * 1000
                            sim = 1.0 - dist
                            logger.info(f"Semantic Cache HIT (DB): sim={sim:.4f} in {elapsed_ms:.2f}ms")
                            return CacheHitResult({
                                "cache_hit": True,
                                "similarity": round(sim, 4),
                                "latency_ms": round(elapsed_ms, 2),
                                "original_query": entry.query_text,
                                "report_markdown": entry.report_markdown,
                                "report_json": entry.report_json,
                                "verification_score": entry.verification_score,
                            })
                except Exception as e:
                    logger.debug(f"pgvector lookup error ({e}); checking in-memory fallback cache.")

        # 2. In-memory fallback lookup
        best_match = None
        highest_sim = -1.0
        for item in self._in_memory_cache:
            exp = item.get("expires_at")
            if exp and exp > now:
                sim = cosine_similarity(query_vector, item["embedding"])
                if sim >= settings.SEMANTIC_CACHE_SIMILARITY_THRESHOLD and sim > highest_sim:
                    highest_sim = sim
                    best_match = item

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        if best_match:
            logger.info(f"Semantic Cache HIT (Mem): sim={highest_sim:.4f} in {elapsed_ms:.2f}ms")
            return CacheHitResult({
                "cache_hit": True,
                "similarity": round(highest_sim, 4),
                "latency_ms": round(elapsed_ms, 2),
                "original_query": best_match["query_text"],
                "report_markdown": best_match["report_markdown"],
                "report_json": best_match["report_json"],
                "verification_score": best_match["verification_score"],
            })

        logger.info(f"Semantic Cache MISS in {elapsed_ms:.2f}ms")
        return None

    def clear_in_memory_cache(self) -> None:
        """Clears local in-memory fallback cache entries (useful for testing)."""
        self._in_memory_cache.clear()

    async def store_report(
        self,
        query: str,
        report_data: dict[str, Any],
        ttl_hours: int | None = None
    ) -> bool:
        """Convenience method to store research report dictionary."""
        return await self.store(
            query_text=query,
            report_markdown=report_data.get("report_markdown", ""),
            report_json=report_data,
            verification_score=report_data.get("verification_score", 1.0),
            ttl_hours=ttl_hours,
        )

    async def store(
        self,
        query_text: str,
        report_markdown: str,
        report_json: dict[str, Any],
        verification_score: float,
        ttl_hours: int | None = None
    ) -> bool:
        """Store verified research report in cache (enforces write gate)."""
        if verification_score < settings.SEMANTIC_CACHE_WRITE_GATE_SCORE:
            logger.info(
                f"Skipping cache store: score {verification_score:.2f} < "
                f"{settings.SEMANTIC_CACHE_WRITE_GATE_SCORE:.2f} write gate."
            )
            return False

        ttl = ttl_hours or settings.SEMANTIC_CACHE_TTL_HOURS
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=ttl)
        query_vector = self._embed_text(query_text)

        # 1. Try PostgreSQL store
        stored_in_db = False
        if db_manager._db_available is not False:
            db_manager.init_engine()
            if db_manager.async_session_factory:
                try:
                    async with db_manager.async_session_factory() as session:
                        entry = SemanticCacheEntry(
                            query_text=query_text,
                            query_embedding=query_vector,
                            report_markdown=report_markdown,
                            report_json=report_json,
                            verification_score=verification_score,
                            expires_at=expires_at
                        )
                        session.add(entry)
                        await session.commit()
                        stored_in_db = True
                        logger.info(f"Report stored in pgvector semantic cache (TTL: {ttl}h).")
                except Exception as e:
                    logger.warning(f"Could not store report in pgvector cache ({e}); storing in memory.")

        # 2. In-memory fallback cache (bounded and expired-pruned)
        if not stored_in_db:
            self._in_memory_cache = [
                item for item in self._in_memory_cache if item.get("expires_at", now) > now
            ]
            if len(self._in_memory_cache) >= 100:
                self._in_memory_cache.pop(0)
            self._in_memory_cache.append({
                "query_text": query_text,
                "embedding": query_vector,
                "report_markdown": report_markdown,
                "report_json": report_json,
                "verification_score": verification_score,
                "expires_at": expires_at
            })
        return True


semantic_cache = SemanticCacheService()

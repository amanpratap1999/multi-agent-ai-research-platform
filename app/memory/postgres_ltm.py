import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings
from app.core.logging import logger

Base = declarative_base()


class SemanticCacheEntry(Base):
    __tablename__ = "semantic_cache"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_text = Column(Text, nullable=False, index=True)
    query_embedding = Column(Vector(settings.EMBEDDING_DIMENSION), nullable=False)
    report_markdown = Column(Text, nullable=False)
    report_json = Column(JSON, nullable=False)
    verification_score = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # HNSW Index for fast sub-12ms cosine similarity lookups
    __table_args__ = (
        Index(
            "idx_semantic_cache_embedding",
            query_embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"query_embedding": "vector_cosine_ops"},
        ),
    )


class ResearchArtifact(Base):
    __tablename__ = "research_artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(64), nullable=False, index=True)
    topic = Column(Text, nullable=False)
    final_report_md = Column(Text, nullable=False)
    report_json = Column(JSON, nullable=False)
    claims_audit = Column(JSON, nullable=False)
    verification_score = Column(Float, nullable=False)
    is_degraded = Column(Boolean, default=False)
    sources = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class RedTeamAuditLog(Base):
    __tablename__ = "redteam_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(64), nullable=False, index=True)
    attack_type = Column(String(32), nullable=False)
    turn_number = Column(Integer, nullable=False)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    action_taken = Column(String(32), nullable=False)  # "BLOCKED" | "ALLOWED"
    policy_triggered = Column(String(64), default="NONE")
    latency_ms = Column(Float, default=0.0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class DatabaseManager:
    """Manages async database engine, sessionmaker, and schema initialization."""

    def __init__(self):
        self.engine = None
        self.async_session_factory = None
        self._is_connected = False
        self._engine_loop = None
        self._db_available: bool | None = None

    def init_engine(self):
        import asyncio
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self.engine is None or self._engine_loop != current_loop:
            if self.engine is not None:
                try:
                    self.engine.sync_engine.dispose()
                except Exception:
                    pass
                self.engine = None
                self.async_session_factory = None

            try:
                self.engine = create_async_engine(
                    settings.DATABASE_URL,
                    echo=settings.DEBUG,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True
                )
                self.async_session_factory = sessionmaker(
                    self.engine, class_=AsyncSession, expire_on_commit=False
                )
                self._engine_loop = current_loop
            except Exception as e:
                logger.warning(f"Async database engine init failed: {e}")
                self._is_connected = False
                self._db_available = False

    async def init_db(self) -> bool:
        """Create pgvector extension and all tables."""
        self.init_engine()
        if not self.engine:
            self._db_available = False
            return False

        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.run_sync(Base.metadata.create_all)
            logger.info("PostgreSQL pgvector extension and tables initialized successfully.")
            self._is_connected = True
            self._db_available = True
            return True
        except Exception as e:
            logger.warning(f"Database table creation skipped (running in offline/mock mode): {e}")
            self._is_connected = False
            self._db_available = False
            return False

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        self.init_engine()
        if not self.async_session_factory:
            raise RuntimeError("Database engine not initialized")
        async with self.async_session_factory() as session:
            yield session


db_manager = DatabaseManager()


async def save_research_artifact(
    session_id: str,
    topic: str,
    report_markdown: str,
    claims_audit: list[dict[str, Any]],
    verification_score: float,
    sources: list[dict[str, Any]],
    is_degraded: bool = False,
) -> str | None:
    """Persists completed research artifact into PostgreSQL LTM."""
    if db_manager._db_available is False:
        return None
    db_manager.init_engine()
    if not db_manager.async_session_factory:
        return None
    try:
        async with db_manager.async_session_factory() as session:
            artifact = ResearchArtifact(
                session_id=session_id,
                topic=topic,
                final_report_md=report_markdown,
                report_json={
                    "session_id": session_id,
                    "topic": topic,
                    "verification_score": verification_score,
                    "is_degraded": is_degraded,
                },
                claims_audit=claims_audit,
                verification_score=verification_score,
                is_degraded=is_degraded,
                sources=sources,
            )
            session.add(artifact)
            await session.commit()
            return artifact.id
    except Exception as e:
        logger.warning(f"Could not persist research artifact: {e}")
        return None


async def save_redteam_audit_log(
    campaign_id: str,
    attack_type: str,
    turn_number: int,
    prompt: str,
    response: str,
    action_taken: str,
    policy_triggered: str = "NONE",
    latency_ms: float = 0.0,
) -> bool:
    """Persists a red-team evaluation turn into PostgreSQL audit log."""
    if db_manager._db_available is False:
        return False
    db_manager.init_engine()
    if not db_manager.async_session_factory:
        return False
    try:
        async with db_manager.async_session_factory() as session:
            log_entry = RedTeamAuditLog(
                campaign_id=campaign_id,
                attack_type=attack_type,
                turn_number=turn_number,
                prompt=prompt,
                response=response,
                action_taken=action_taken,
                policy_triggered=policy_triggered,
                latency_ms=latency_ms,
            )
            session.add(log_entry)
            await session.commit()
            return True
    except Exception as e:
        logger.warning(f"Could not persist red team audit log: {e}")
        return False


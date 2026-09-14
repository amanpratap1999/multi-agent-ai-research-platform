from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.defense.bedrock_guardrail import BedrockGuardrailClient, guardrail_client
from app.gateway.client import UnifiedLLMGateway, gateway
from app.memory.postgres_ltm import db_manager
from app.memory.redis_stm import redis_stm


async def get_db_session() -> AsyncGenerator[AsyncSession | None, None]:
    """Yields an active database session or None if running offline."""
    if db_manager._is_connected and db_manager.async_session_factory:
        async with db_manager.async_session_factory() as session:
            yield session
    else:
        yield None


def get_redis_client():
    return redis_stm.get_client()


def get_llm_gateway() -> UnifiedLLMGateway:
    return gateway


def get_guardrail_client() -> BedrockGuardrailClient:
    return guardrail_client

import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import logger


class RedisSTMManager:
    """Manages Short-Term Memory (STM) session state and LangGraph checkpointing."""

    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._redis_loop = None
        self._in_memory_store: dict[str, dict[str, Any]] = {}

    async def get_redis(self) -> aioredis.Redis | None:
        import asyncio
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._redis is None or self._redis_loop != current_loop:
            if self._redis is not None:
                try:
                    await self._redis.aclose()
                except Exception:
                    pass
                self._redis = None
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2.0
                )
                self._redis_loop = current_loop
                await self._redis.ping()
            except Exception as e:
                logger.warning(f"Redis STM offline ({e}); using local memory store.")
                self._redis = None
                self._redis_loop = None
        return self._redis

    async def save_session_state(self, session_id: str, state: dict[str, Any], ttl_seconds: int = 86400) -> None:
        """Persist intermediate agent state to Redis STM."""
        r = await self.get_redis()
        serialized = json.dumps(state, default=str)
        if r is not None:
            try:
                await r.setex(f"session:{session_id}", ttl_seconds, serialized)
                return
            except Exception as e:
                logger.error(f"Failed to set session state in Redis: {e}")
        self._in_memory_store[session_id] = state

    # Aliases for compatibility
    set_session_state = save_session_state

    async def get_session_state(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve intermediate agent state from Redis STM."""
        r = await self.get_redis()
        if r is not None:
            try:
                val = await r.get(f"session:{session_id}")
                if val:
                    return json.loads(val)
            except Exception as e:
                logger.error(f"Failed to get session state from Redis: {e}")
        return self._in_memory_store.get(session_id)

    async def delete_session_state(self, session_id: str) -> None:
        """Clear session state upon completion or expiry."""
        r = await self.get_redis()
        if r is not None:
            try:
                await r.delete(f"session:{session_id}")
            except Exception as e:
                logger.error(f"Failed to delete session state in Redis: {e}")
        self._in_memory_store.pop(session_id, None)


redis_stm = RedisSTMManager()

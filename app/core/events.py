import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import logger


class EventBroadcaster:
    """Publishes and streams events using Redis Streams (XADD / XREAD) for durable SSE delivery."""

    def __init__(self):
        self._redis: aioredis.Redis | None = None
        self._redis_loop = None
        self._fallback_queues: dict[str, asyncio.Queue] = {}

    async def get_redis(self) -> aioredis.Redis | None:
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
                logger.warning(f"Redis connection failed ({e}); using in-process event queues.")
                self._redis = None
                self._redis_loop = None
        return self._redis

    async def publish_event(
        self,
        session_id: str = "",
        event_type: str = "message",
        data: dict[str, Any] | None = None,
        stream_key: str | None = None
    ) -> str:
        """Publish an event to a Redis Stream with automatic serialization."""
        key = session_id or stream_key or "default_stream"
        payload = {
            "type": event_type,
            "data": json.dumps(data or {})
        }
        r = await self.get_redis()
        if r is not None:
            try:
                msg_id = await r.xadd(key, payload, maxlen=1000)
                return msg_id
            except Exception as e:
                logger.error(f"Failed to xadd to Redis stream {key}: {e}")

        # In-process fallback
        import time as _time
        if key not in self._fallback_queues:
            self._fallback_queues[key] = asyncio.Queue()
        msg_id = f"{int(_time.time() * 1000)}-0"
        await self._fallback_queues[key].put((msg_id, event_type, data or {}))
        return msg_id

    async def stream_events(
        self,
        session_id: str,
        last_event_id: str | None = None
    ) -> AsyncGenerator[str, None]:
        """Formats SSE chunks directly from Redis Streams for FastAPI StreamingResponse."""
        async for event in self.subscribe_stream(stream_key=session_id, last_id=last_event_id or "0-0"):
            try:
                inner_data = json.loads(event["data"]) if isinstance(event["data"], str) else event["data"]
            except Exception:
                inner_data = event["data"]
            envelope = json.dumps({
                "type": event["event"],
                "data": inner_data,
            })
            chunk = f"id: {event['id']}\nevent: message\ndata: {envelope}\n\n"
            yield chunk

    async def subscribe_stream(
        self,
        stream_key: str,
        last_id: str = "0-0",
        block_ms: int = 15000
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Async generator yielding SSE events from Redis Streams, supporting Last-Event-ID replay."""
        r = await self.get_redis()
        current_id = last_id if last_id and last_id != "$" else "0-0"

        if r is not None:
            while True:
                try:
                    # Read from stream
                    events = await r.xread({stream_key: current_id}, count=10, block=block_ms)
                    if not events:
                        # Emit keep-alive ping on timeout
                        yield {"event": "ping", "data": "{}", "id": current_id}
                        continue

                    for _, messages in events:
                        for msg_id, fields in messages:
                            current_id = msg_id
                            event_type = fields.get("type", "message")
                            raw_data = fields.get("data", "{}")
                            try:
                                parsed_data = json.loads(raw_data)
                            except Exception:
                                parsed_data = {"raw": raw_data}

                            yield {
                                "id": msg_id,
                                "event": event_type,
                                "data": json.dumps(parsed_data)
                            }
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error reading Redis stream {stream_key}: {e}")
                    await asyncio.sleep(1.0)
                    yield {"event": "ping", "data": "{}", "id": current_id}
        else:
            # In-process queue generator
            queue = self._fallback_queues.setdefault(stream_key, asyncio.Queue())
            while True:
                try:
                    msg_id, event_type, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield {
                        "id": msg_id,
                        "event": event_type,
                        "data": json.dumps(data)
                    }
                except TimeoutError:
                    yield {"event": "ping", "data": "{}", "id": "0-0"}
                except asyncio.CancelledError:
                    break


event_broadcaster = EventBroadcaster()

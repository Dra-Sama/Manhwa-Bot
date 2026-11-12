# Code By @V_Sbotmaker (on Telegram)
"""
Tools/redis_queue.py — Redis-backed persistent task queue

Design:
  * Uses Redis LPUSH / BRPOP for reliable FIFO queuing of task metadata.
  * TaskCard objects are NOT serialized to Redis (they hold live asyncio state
    and Pyrogram objects). Only the task *metadata* (task_id, user_id,
    chapter URLs, settings snapshot) is persisted.
  * On restart the bot replays pending task metadata from Redis and re-enqueues
    them into the in-memory AQueue. This gives crash-safe persistence without
    needing to serialize complex Python objects.
  * Graceful fallback: if Redis is unreachable at startup the module logs a
    warning and silently disables persistence. The bot still runs purely in-
    memory (same as the old behaviour).

Usage:
  from Tools.redis_queue import rq
  await rq.push(task_id, payload_dict)
  await rq.ack(task_id)          # remove after successful processing
  await rq.replay(callback)      # on startup, re-enqueue survivors
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Callable, Dict, Optional

from loguru import logger

_REDIS_URL          = os.environ.get("REDIS_URL", "rediss://default:gQAAAAAAAqPJAAIgcDI2YWI5NTFkNjBlZjM0NzBmYjA5Zjg4NWQwNDVmOWVjZQ@eminent-satyr-173001.upstash.io:6379")
_QUEUE_KEY          = "amanhwa:task_queue"
_PROCESSING_KEY     = "amanhwa:processing"   # hash: task_id -> payload JSON
_TASK_TTL           = 86400 * 3              # 3 days max lifetime


class _NoopQueue:
    """Silent no-op when Redis is unavailable."""

    async def push(self, task_id: str, payload: Dict[str, Any]) -> None:
        pass

    async def ack(self, task_id: str) -> None:
        pass

    async def replay(self, callback: Callable) -> None:
        pass

    async def length(self) -> int:
        return 0

    async def close(self) -> None:
        pass

    @property
    def available(self) -> bool:
        return False


class RedisQueue:
    """Async Redis-backed task queue using aioredis/redis.asyncio."""

    def __init__(self, redis_url: str):
        self._url   = redis_url
        self._redis = None
        self._lock  = asyncio.Lock()

    # ── lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        try:
            import redis.asyncio as aioredis  # type: ignore
            self._redis = await aioredis.from_url(
                self._url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )
            await self._redis.ping()
            logger.info(f"[RedisQueue] Connected to Redis at {self._url}")
            return True
        except Exception as e:
            logger.warning(f"[RedisQueue] Cannot connect to Redis: {e} — running without persistence")
            self._redis = None
            return False

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass

    @property
    def available(self) -> bool:
        return self._redis is not None

    # ── queue operations ────────────────────────────────────────────────────────

    async def push(self, task_id: str, payload: Dict[str, Any]) -> None:
        """
        Enqueue a task.
        payload should contain everything needed to reconstruct the task on replay:
          task_id, user_id, chapter_urls, settings, webs_sf, etc.
        """
        if not self._redis:
            return
        try:
            async with self._lock:
                data = json.dumps(payload, default=str)
                # Store in processing hash (survives crashes) and push to list
                pipe = self._redis.pipeline()
                pipe.hset(_PROCESSING_KEY, task_id, data)
                pipe.lpush(_QUEUE_KEY, task_id)
                pipe.expire(_QUEUE_KEY, _TASK_TTL)
                await pipe.execute()
        except Exception as e:
            logger.warning(f"[RedisQueue] push failed for {task_id}: {e}")

    async def ack(self, task_id: str) -> None:
        """Remove a task from the processing hash once it completes successfully."""
        if not self._redis:
            return
        try:
            await self._redis.hdel(_PROCESSING_KEY, task_id)
        except Exception as e:
            logger.warning(f"[RedisQueue] ack failed for {task_id}: {e}")

    async def replay(self, callback: Callable[[Dict[str, Any]], Any]) -> None:
        """
        On startup, iterate all tasks in the processing hash (those that were
        interrupted by a crash) and call `callback(payload)` for each.
        The callback is responsible for re-creating and re-enqueuing the TaskCard.
        """
        if not self._redis:
            return
        try:
            survivors = await self._redis.hgetall(_PROCESSING_KEY)
            if not survivors:
                return
            logger.info(f"[RedisQueue] Replaying {len(survivors)} interrupted task(s) from Redis")
            for task_id, data_str in survivors.items():
                try:
                    payload = json.loads(data_str)
                    await callback(payload)
                except Exception as e:
                    logger.warning(f"[RedisQueue] replay failed for {task_id}: {e}")
                    # Remove unrecoverable tasks so they don't loop forever
                    await self._redis.hdel(_PROCESSING_KEY, task_id)
        except Exception as e:
            logger.warning(f"[RedisQueue] replay scan failed: {e}")

    async def length(self) -> int:
        if not self._redis:
            return 0
        try:
            return await self._redis.llen(_QUEUE_KEY)
        except Exception:
            return 0


# ── Module singleton ───────────────────────────────────────────────────────────

rq: RedisQueue | _NoopQueue = _NoopQueue()


async def init_redis_queue() -> None:
    """
    Called once at startup from main.py.
    Replaces the module-level `rq` singleton with a live RedisQueue if a
    REDIS_URL env var is set and the connection succeeds.
    """
    global rq

    if not _REDIS_URL:
        logger.info("[RedisQueue] REDIS_URL not set — persistence disabled (in-memory only)")
        return

    candidate = RedisQueue(_REDIS_URL)
    if await candidate.connect():
        rq = candidate
    # else: rq remains _NoopQueue, logs already emitted inside connect()


async def close_redis_queue() -> None:
    """Called at bot shutdown."""
    await rq.close()

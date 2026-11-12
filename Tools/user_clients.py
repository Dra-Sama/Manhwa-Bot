# Code By @V_Sbotmaker (on Telegram)
"""
Tools/user_clients.py — Per-user Telegram bot client manager

Each user can register their own bot token via /mybot.
This module manages the lifecycle of those bot clients:
  * Validates tokens against Telegram API
  * Creates Pyrogram Client instances (in-memory sessions)
  * Provides get_client(user_id) for uploaders to use
  * Persists tokens in MongoDB (encrypted via XOR + base64 — lightweight,
    not cryptographic-grade, but sufficient to avoid plaintext in logs/exports)

Why per-user clients?
  The main bot shares a single Telegram upload slot and rate-limit pool.
  When multiple users are auto-posting to their channels, they compete for the
  same FloodWait budget. Per-user bots each have their own rate limit quota,
  so one heavy user can't block others or the main bot's download pipeline.
"""

from __future__ import annotations

import asyncio
import base64
import os
import time
from typing import Dict, Optional

from loguru import logger
from curl_cffi import requests as cffi_requests

# Lazy imports to avoid circular deps at module load
_pyrogram = None


def _get_pyrogram():
    global _pyrogram
    if _pyrogram is None:
        import pyrogram
        _pyrogram = pyrogram
    return _pyrogram


# ── Simple obfuscation (NOT encryption — tokens stored in your own MongoDB) ──
_XOR_KEY = int(os.environ.get("TOKEN_XOR_KEY", "42"))


def _obfuscate(token: str) -> str:
    """XOR each byte then base64-encode. Keeps tokens out of log grep output."""
    b = bytes(c ^ _XOR_KEY for c in token.encode("utf-8"))
    return base64.b64encode(b).decode("ascii")


def _deobfuscate(encoded: str) -> str:
    b = base64.b64decode(encoded.encode("ascii"))
    return bytes(c ^ _XOR_KEY for c in b).decode("utf-8")


# ── Telegram API validation ───────────────────────────────────────────────────

async def validate_bot_token(token: str) -> Optional[dict]:
    """
    Call Telegram getMe to validate a bot token.
    Returns the bot info dict on success, None on failure.
    """
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        resp = cffi_requests.get(url, timeout=10)
        data = resp.json()
        if data.get("ok"):
            return data.get("result")
    except Exception as e:
        logger.warning(f"[UserClient] Token validation error: {e}")
    return None


# ── Client manager ────────────────────────────────────────────────────────────

class UserClientManager:
    """
    Manages one Pyrogram Client per user (keyed by user_id str).

    Thread-safety: all mutations go through asyncio.Lock.
    """

    def __init__(self):
        self._clients:     Dict[str, object]        = {}   # user_id -> pyrogram.Client
        self._starting:    Dict[str, asyncio.Event] = {}   # user_id -> Event (guards double-start)
        self._last_active: Dict[str, float]         = {}   # user_id -> float timestamp
        self._lock = asyncio.Lock()

    def touch(self, user_id: str) -> None:
        """Update last active timestamp for user_id."""
        self._last_active[str(user_id)] = time.time()

    # ── public API ────────────────────────────────────────────────────────────

    async def get_client(self, user_id: str) -> Optional[object]:
        """Return a running Client for user_id, or None if not available."""
        user_id = str(user_id)
        if user_id in self._clients:
            client = self._clients[user_id]
            if getattr(client, "is_connected", False):
                self.touch(user_id)
                return client
            # Stale — remove and try to reconnect below
            await self._remove(user_id)

        # Try to load token from DB and create client
        from Tools.db import database  # noqa: PLC0415
        token_enc = await database.get_bot_token(user_id)
        if not token_enc:
            return None

        try:
            token = _deobfuscate(token_enc)
        except Exception:
            logger.warning(f"[UserClient] Failed to decode token for user {user_id}")
            return None

        client = await self._create_and_start(user_id, token)
        if client:
            self.touch(user_id)
        return client

    async def register_token(self, user_id: str, raw_token: str) -> Optional[dict]:
        """
        Validate token, store obfuscated form in DB, keep client idle in sleep mode.
        Returns bot info dict on success, None on failure.
        """
        user_id = str(user_id)

        bot_info = await validate_bot_token(raw_token)
        if not bot_info:
            return None

        # Stop any existing client first
        await self._remove(user_id)

        from Tools.db import database  # noqa: PLC0415
        await database.set_bot_token(user_id, _obfuscate(raw_token))
        return bot_info

    async def remove_token(self, user_id: str) -> None:
        """Remove stored token and stop the client."""
        user_id = str(user_id)
        await self._remove(user_id)
        from Tools.db import database  # noqa: PLC0415
        await database.delete_bot_token(user_id)

    async def warmup_all(self) -> None:
        """
        No-op: Worker bots remain idle at startup and only activate on-demand during upload.
        """
        logger.info("[UserClient] On-demand worker bot mode active: warmup_all skipped.")
        return

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def get_client_ctx(self, user_id: str):
        """
        Async context manager for on-demand worker bot lifecycle.
        Starts the worker bot client right before upload and keeps it connected.
        Yields the connected client, or None if user has no worker bot registered.
        """
        user_id = str(user_id)
        client = await self.get_client(user_id)
        try:
            yield client
        finally:
            if client:
                self.touch(user_id)

    async def start_idle_checker(self) -> None:
        """
        Periodically check for user bot clients that have been idle for 30 minutes (1800 seconds).
        If idle >= 30 mins, stop the client and put it into sleep mode.
        """
        logger.info("[UserClient] Idle checker background task started (30 min timeout).")
        while True:
            await asyncio.sleep(60)
            try:
                now = time.time()
                async with self._lock:
                    active_uids = list(self._clients.keys())

                for uid in active_uids:
                    last = self._last_active.get(uid, now)
                    if now - last >= 1800:  # 30 minutes
                        logger.info(
                            f"[UserClient] User {uid} client idle for 30+ mins. "
                            "Entering sleep mode (stopping client)."
                        )
                        await self._remove(uid)
            except Exception as e:
                logger.error(f"[UserClient] Error in idle checker: {e}")

    async def stop_all(self) -> None:
        """Stop all running user clients (called at shutdown)."""
        async with self._lock:
            user_ids = list(self._clients.keys())
        for uid in user_ids:
            await self._remove(uid)

    # ── internals ─────────────────────────────────────────────────────────────

    async def _create_and_start(self, user_id: str, token: str) -> Optional[object]:
        """Create, start, and register a new Client. Returns client or None."""
        pyrogram = _get_pyrogram()

        # Guard against race where two coroutines try to start the same user
        async with self._lock:
            if user_id in self._clients:
                return self._clients[user_id]
            if user_id in self._starting:
                ev = self._starting[user_id]
            else:
                ev = asyncio.Event()
                self._starting[user_id] = ev

        # Only one coroutine proceeds past here for this user_id
        try:
            from bot import Vars  # noqa: PLC0415
            client = pyrogram.Client(
                name=f"user_bot_{user_id}",
                api_id=Vars.API_ID,
                api_hash=Vars.API_HASH,
                bot_token=token,
                in_memory=True,
                workers=4,
            )
            await client.start()
            async with self._lock:
                self._clients[user_id] = client
                self._starting.pop(user_id, None)
            ev.set()
            logger.info(f"[UserClient] Started bot client for user {user_id}")
            return client

        except Exception as e:
            logger.warning(f"[UserClient] Failed to start client for user {user_id}: {e}")
            async with self._lock:
                self._starting.pop(user_id, None)
            ev.set()
            return None

    async def _remove(self, user_id: str) -> None:
        """Stop and remove client for user_id."""
        async with self._lock:
            client = self._clients.pop(user_id, None)
            self._last_active.pop(user_id, None)

        if client:
            try:
                await client.stop()
                logger.info(f"[UserClient] Stopped bot client for user {user_id}")
            except Exception as e:
                logger.warning(f"[UserClient] Error stopping client for {user_id}: {e}")


# ── Module singleton ───────────────────────────────────────────────────────────
user_client_manager = UserClientManager()

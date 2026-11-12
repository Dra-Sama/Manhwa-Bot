# Code By @V_Sbotmaker (on Telegram)
"""
Webs/source_manager.py - Source failure & health management with retries
"""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Any, Optional
from loguru import logger

from bot import Bot, Vars
from Tools.db import database
from TG.storage import retry_on_flood


async def notify_source_disabled(sf: str, name: str, url: str, last_error: str, now_utc: str) -> None:
    """Send single notification to Bot Owner and all configured Bot Admins when a source is auto-disabled."""
    notification_text = (
        f"<b>⚠️ Source Automatically Disabled</b>\n\n"
        f"<b>Source:</b> {name}\n"
        f"<b>URL:</b> {url or 'N/A'}\n"
        f"<b>Reason:</b> Repeated request failures\n"
        f"<b>Retry Attempts:</b> 3/3\n"
        f"<b>Last Error:</b> <code>{last_error or 'Unknown error'}</code>\n"
        f"<b>Status:</b> Automatically Disabled\n"
        f"<b>Time:</b> {now_utc}\n\n"
        f"Please check and fix the source before enabling it again."
    )

    recipients = set()
    if getattr(Vars, "ADMINS", None):
        for admin in Vars.ADMINS:
            try:
                recipients.add(int(admin))
            except (ValueError, TypeError):
                pass

    if getattr(Vars, "OWNER", None):
        try:
            recipients.add(int(Vars.OWNER))
        except (ValueError, TypeError):
            pass

    for user_id in recipients:
        try:
            await retry_on_flood(Bot.send_message)(user_id, notification_text)
            logger.info(f"[SourceManager] Sent auto-disable alert to admin/owner {user_id} for source '{name}'")
        except Exception as e:
            logger.warning(f"[SourceManager] Failed to send alert to {user_id}: {e}")


async def execute_source_with_retry(
    sf: str,
    name: str,
    url: str,
    func: Callable[..., Any],
    *args: Any,
    user_id: Optional[Any] = None,
    **kwargs: Any
) -> Any:
    """
    Execute a source function (e.g. search, get_chapters, get_images) with up to 3 retries.
    If it fails 3 consecutive times, automatically mark source as auto_disabled and notify admins once.
    """
    # 1. Check if source is globally enabled
    if not await database.is_source_globally_enabled(sf):
        logger.info(f"[SourceManager] Skipping '{name}' ({sf}): Source is globally auto/manually disabled.")
        return None

    # 2. Check if source is enabled for specific user (if user_id provided)
    if user_id and not await database.is_source_enabled_for_user(user_id, sf):
        logger.info(f"[SourceManager] Skipping '{name}' ({sf}): Source is disabled for user {user_id}.")
        return None

    max_retries = 3
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            res = await func(*args, **kwargs)
            # If function returned valid data (or empty list if legitimate), treat as success
            if res is not None:
                return res
            last_error = "Empty or None response from source"
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[SourceManager] Source '{name}' ({sf}) attempt {attempt}/{max_retries} failed: {e}")

        if attempt < max_retries:
            await asyncio.sleep(1.5 * attempt)

    # All 3 retries failed -> Auto-disable source in DB
    logger.error(f"[SourceManager] Source '{name}' ({sf}) failed all {max_retries} retries. Auto-disabling.")
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    transitioned = await database.auto_disable_source(sf=sf, name=name, url=url, last_error=last_error)
    if transitioned:
        await notify_source_disabled(sf=sf, name=name, url=url, last_error=last_error, now_utc=now_utc)

    return None

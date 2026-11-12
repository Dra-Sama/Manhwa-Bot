# Code By @V_Sbotmaker (on Telegram)
"""
TG/migration_alert.py — One-time migration alert for existing channel users

Sent once to users who have target/auto channels configured but haven't
added their own bot token yet. After the alert is sent, `bot_token_alert_sent`
is set to True so it never fires again for that user.

Call `schedule_migration_alerts()` from main.py once at startup.
"""

import asyncio
from loguru import logger

from bot import Bot, Vars
from Tools.db import database


_ALERT_TEXT = """\
<blockquote><b>📢 Important Update</b></blockquote>

Hi! We've made a change to how channel auto-uploads work.

<b>Starting now, each user needs their own Telegram bot token</b> for auto-posting to their channels (so your uploads don't compete with others for rate limits).

<b>How to add your bot token:</b>
1. Create a bot at @BotFather and get the token
2. Add the bot as admin to your channel
3. Send me: <code>/mybot YOUR_BOT_TOKEN</code>

Until you add a token, auto-uploads to your channels will be paused.

➥ Need help? Contact @WizardBotHelper\
"""


async def _send_alert_to_user(user_id: str) -> bool:
    try:
        await Bot.send_message(int(user_id), _ALERT_TEXT)
        await database.mark_alert_sent(user_id)
        logger.info(f"[MigrationAlert] Sent to user {user_id}")
        return True
    except Exception as e:
        logger.warning(f"[MigrationAlert] Failed to send to {user_id}: {e}")
        return False


async def run_migration_alerts() -> None:
    """
    Iterate users needing the migration alert and send messages.
    Throttled to 1 per second to avoid Telegram flood.
    """
    count = 0
    try:
        async for user_doc in database.get_users_needing_alert():
            user_id = str(user_doc.get("_id", ""))
            if not user_id:
                continue
            await _send_alert_to_user(user_id)
            count += 1
            await asyncio.sleep(1.2)   # ~50 messages/min, well under Telegram limit
    except Exception as e:
        logger.exception(f"[MigrationAlert] Error during sweep: {e}")

    logger.info(f"[MigrationAlert] Done — sent {count} alert(s)")


def schedule_migration_alerts() -> None:
    """
    Fire-and-forget: create the alert sweep as a background asyncio Task.
    Safe to call from startup code (doesn't block Bot.run()).
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(run_migration_alerts())
    except RuntimeError:
        pass   # no loop yet — skip silently (unit tests)

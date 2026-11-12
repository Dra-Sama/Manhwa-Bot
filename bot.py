# Code By @V_Sbotmaker (on Telegram)
import asyncio
import random
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import pyrogram
from curl_cffi.requests import AsyncSession
from loguru import logger
from pyrogram.enums import ButtonStyle
from pyrogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup

from config import *

ANNOUNCE_CHAT_ID = Vars.LOG_CHANNEL
CHANNEL_URL = "https://telegram.me/Wizard_Bots"

BANNER = """

    ██╗    ██╗██╗███████╗ █████╗ ██████╗ ██████╗     ██████╗  ██████╗ ████████╗███████╗
    ██║    ██║██║╚══███╔╝██╔══██╗██╔══██╗██╔══██╗    ██╔══██╗██╔═══██╗╚══██╔══╝██╔════╝
    ██║ █╗ ██║██║  ███╔╝ ███████║██████╔╝██║  ██║    ██████╔╝██║   ██║   ██║   ███████╗
    ██║███╗██║██║ ███╔╝  ██╔══██║██╔══██╗██║  ██║    ██╔══██╗██║   ██║   ██║   ╚════██║
    ╚███╔███╔╝██║███████╗██║  ██║██║  ██║██████╔╝    ██████╔╝╚██████╔╝   ██║   ███████║
     ╚══╝╚══╝ ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝     ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝

"""

STOP_MSG = """
<blockquote> <b>🥀 Manga Bot is Down 😴 </blockquote>

<blockquote> 🥀 Make By @Wizard_Bots</b> </blockquote>
"""


class TimeoutError(Exception):
    pass


def load_fsb_vars(bot: "Manhwa_Bot") -> None:
    try:
        for entry in Vars.FORCE_SUB_CHANNEL.split(","):
            name, value = entry.strip().split(":", 1)
            bot.FSB.append((name, value))
    except Exception:
        logger.error(" FORCE_SUB_CHANNEL is not set correctly! ")
        sys.exit()


async def get_country_ipapi() -> dict[str, str | None]:
    """Get IP/country info with a single request (ip-api detects the caller's IP)."""
    try:
        async with AsyncSession() as session:
            response = await session.get("http://ip-api.com/json/", timeout=5)
    except Exception as e:
        return {"error": str(e)}

    if response.status_code != 200:
        return {"error": f"HTTP {response.status_code}"}

    data = response.json()

    if data.get("status") == "fail":
        return {"error": data.get("message", "Lookup failed")}

    return {
        "ip": data.get("query"),
        "country": data.get("country"),
        "country_code": data.get("countryCode"),
        "region": data.get("regionName"),
        "city": data.get("city"),
        "isp": data.get("isp"),
        "org": data.get("org"),
    }


async def _close_scraper() -> None:
    from Webs.scraper import shared_scraper

    await shared_scraper.close()


async def _close_ihandler() -> None:
    from Tools.ihandler import ihandler

    await ihandler.cleanup()


async def _close_db() -> None:
    from Tools.db import database

    await database.close()


async def _safe_close(name: str, closer: Callable) -> None:
    try:
        await closer()
    except Exception as e:
        logger.error(f"Error closing {name}: {e}")


class Manhwa_Bot(pyrogram.Client):
    def __init__(self) -> None:
        super().__init__(
            "ManhwaBot",
            api_id=Vars.API_ID,
            api_hash=Vars.API_HASH,
            bot_token=Vars.BOT_TOKEN,
            plugins=Vars.plugins,
            workers=100,
            in_memory=True
        )

        self.__version__ = pyrogram.__version__
        self.FSB: list[tuple[str, str]] = []
        self.listerner: dict[int, dict] = {}
        self.county_info: dict[str, str | None] = {}
        self.web_process: asyncio.subprocess.Process | None = None
        self.username: str = ""

    async def _load_country_info(self) -> None:
        self.county_info = await get_country_ipapi()

    async def _run_web(self) -> None:
        self.web_process = await asyncio.create_subprocess_exec(
            "gunicorn",
            "app:app",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        logger.info("Web app started successfully")

    async def _announce(self, caption: str, buttons: list[InlineKeyboardButton]) -> None:
        try:
            await self.send_photo(
                chat_id=ANNOUNCE_CHAT_ID,
                photo=random.choice(Vars.PICS),
                caption=caption,
                reply_markup=InlineKeyboardMarkup([buttons])
            )
        except Exception as e:
            logger.warning(f"Announcement failed: {e}")

    async def _set_commands(self) -> None:
        try:
            from TG.queue import botcommands

            await self.set_bot_commands([BotCommand(k, v) for k, v in botcommands.items()])
            logger.info("Bot commands have been set up automatically.")
        except Exception as e:
            logger.error(f"Failed to set auto bot commands: {e}")

    async def _notify_restart(self) -> None:
        restart_file = Path("restart_msg.txt")

        if not restart_file.exists():
            return

        try:
            chat_id, message_id = restart_file.read_text().split(":")
            await self.edit_message_text(
                chat_id=int(chat_id),
                message_id=int(message_id),
                text="<code>Restarted Successfully</code>"
            )
        except Exception as e:
            logger.exception(e)

        restart_file.unlink(missing_ok=True)

    async def start(self, *a, **k) -> None:
        await super().start(*a, **k)

        me = await self.get_me()
        self.bot_id = me.id
        self.username = me.username

        # Non-blocking: runs in the background instead of delaying startup
        asyncio.create_task(self._load_country_info())

        await self._notify_restart()
        shutil.rmtree("Process", ignore_errors=True)

        if Vars.FORCE_SUB_CHANNEL:
            load_fsb_vars(self)

        logger.info(BANNER)
        logger.info("Make By https://t.me/Wizard_Bots ")
        logger.info(f"Manhwa Bot Started as {me.first_name} | @{me.username}")

        if Vars.WEBS_HOST:
            asyncio.create_task(self._run_web())

        await self._set_commands()

        msg = f"""<blockquote><b>🔥 SYSTEMS ONLINE. READY TO RUMBLE. 🔥

DC Mode: {me.dc_id}

Sleep mode deactivated. Neural cores at 100%. Feed me tasks, and watch magic happen. Let’s. Get. Dangerous.</b></blockquote>"""

        buttons = [
            InlineKeyboardButton(
                "*Start Now*",
                url=f"https://t.me/{self.username}?start=start",
                style=ButtonStyle.DANGER
            ),
            InlineKeyboardButton("*Channel*", url=CHANNEL_URL)
        ]
        await self._announce(msg, buttons)

    async def listen(
        self,
        user_id: int,
        timeout: int = 70,
        filters: Callable | None = None
    ) -> object | None:
        """Wait for a message from a specific chat with optional filters."""

        if user_id in self.listerner:
            return None

        future = asyncio.get_running_loop().create_future()
        self.listerner[user_id] = {
            "timeout": timeout,
            "filters": filters,
            "future": future
        }

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except (TimeoutError,  asyncio.TimeoutError): #noqa
            raise TimeoutError() from None
        finally:
            self.listerner.pop(user_id, None)

    async def stop(self, *a, **k) -> None:
        logger.info("Manhwa Bot Stopping")

        buttons = [
            InlineKeyboardButton("sᴛᴀʀᴛ ᴍᴇ", url=f"https://t.me/{self.username}?start=start"),
            InlineKeyboardButton("ᴜᴘᴅᴀᴛᴇs", url=CHANNEL_URL)
        ]
        await self._announce(STOP_MSG, buttons)

        if self.web_process and self.web_process.returncode is None:
            self.web_process.terminate()

        await asyncio.gather(
            _safe_close("scraper", _close_scraper),
            _safe_close("ihandler", _close_ihandler),
            _safe_close("database", _close_db)
        )

        await super().stop(*a, **k)


Bot = Manhwa_Bot()

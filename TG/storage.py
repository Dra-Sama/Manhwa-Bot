# Code By @V_Sbotmaker (on Telegram)
import asyncio
import sys

import pyrogram.errors
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import Vars
from Tools.base import ( #noqa
    queue, igrone_error, get_episode_number, retry_on_flood,
    TTLCache, log as log_fu
)
from Webs import web_data

_TTL = 7200

searchs = TTLCache(default_timeout=_TTL)
backs = TTLCache(default_timeout=_TTL)
chaptersList = TTLCache(default_timeout=_TTL)
_storage = TTLCache(default_timeout=_TTL)
pagination = TTLCache(default_timeout=_TTL)
subscribes = TTLCache(default_timeout=_TTL)

search_storage_cache = TTLCache(default_timeout=_TTL, cleanup_interval=60)  # search.py
function_cache = TTLCache(default_timeout=300, cleanup_interval=60)  # search.py

Listeing_cache: dict[str, object] = {}

web_data = dict(sorted(web_data.items()))
plugins_name = " ".join(web.sf for web in web_data.values())

# Precomputed lookups (web_data never changes after the sort above)
_WEBS = tuple(web_data.values())
_WEB_BY_SF = {web.sf: web for web in reversed(_WEBS)}  # reversed => first match wins

_invite_cache: dict[int, str] = {}

_SMALL_CAPS = "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ"
_PLAIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-"
_FANCY = _SMALL_CAPS * 2 + "𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿−"
_FANCY_MAP = str.maketrans(_PLAIN, _FANCY)

_CALLBACK_PREFIX = {"updates": "udat", "gens": "gens", "subs": "isubs"}

_PREFERRED_PRIORITY = {
    slug: index
    for index, slug in enumerate(
        (
            "official",
            "utoon",
            "templescan",
            "lunatoon",
            "magusmanga",
            "asura",
            "asurascan",
            "violetscan",
            "luacomic"
        )
    )
}
_NO_PRIORITY = len(_PREFERRED_PRIORITY)


def get_cache() -> int:
    objects = (
        searchs,
        backs,
        chaptersList,
        _storage,
        pagination,
        subscribes,
        Listeing_cache,
        web_data,
        plugins_name,
        search_storage_cache,
        function_cache
    )

    try:
        return sum(sys.getsizeof(obj) for obj in objects)
    except Exception:
        return 0


def iter_chapters(data: dict, page: int = 1) -> list:
    chapters = data.get("chapters", [])

    if page == 1 or not chapters:
        return chapters

    return chapters[(page - 1) * 60 : page * 60]


def split_list(li: list, chunk_size: int = 2, page: int = 0) -> list:
    """Split `li` into chunks of `chunk_size`.

    page=0 returns every chunk as a list of lists; page>=1 returns just that
    page's items, e.g. split_list([1..10], 3, 2) -> [4, 5, 6].
    """

    if page == 0:
        return [li[i : i + chunk_size] for i in range(0, len(li), chunk_size)]

    start = (page - 1) * chunk_size

    return li[start : start + chunk_size]


def is_listening_(flt, _, message: Message) -> bool:
    user = message.from_user

    if not user or not flt.is_private or not flt.forwarded:
        return False

    return str(user.id) in Listeing_cache and message.text != "/stop"


def check_get_web(url: str | None):
    if not url:
        return None

    return next((web for web in _WEBS if url.startswith(web.url)), None)


def get_webs(sf: str):
    return _WEB_BY_SF.get(sf)


def translation(text: str) -> str:
    return text.translate(_FANCY_MAP)


async def _auth_query(flt, _, query) -> bool:
    reply = query.message.reply_to_message

    if not reply:
        return True

    while reply.from_user and getattr(reply.from_user, "is_bot", False) and reply.reply_to_message:
        reply = reply.reply_to_message

    if not reply.from_user:
        return False

    if reply.from_user.id != query.from_user.id:
        await query.answer("This is not for you", show_alert=True)
        return False

    return True


_AUTH_QUERY = filters.create(_auth_query)


def is_auth_query():
    return _AUTH_QUERY


async def _no_sources() -> list[str]:
    return []


async def plugins_list(
    type: str | None = None,
    page: int = 1,
    user_id: int | None = None
) -> InlineKeyboardMarkup:
    from Tools.db import database

    user_sources = database.get_user_disabled_sources(user_id) if user_id else _no_sources()
    health_data, disabled = await asyncio.gather(database.get_all_sources_health(), user_sources)
    disabled_user_sources = set(disabled)

    prefix = _CALLBACK_PREFIX.get(type, "plugin")
    buttons = []

    for name, web in web_data.items():
        sf = web.sf

        # Skip globally auto-disabled sources and sources the user turned off
        if health_data.get(sf, {}).get("status") == "auto_disabled" or sf in disabled_user_sources:
            continue

        buttons.append(InlineKeyboardButton(name, callback_data=f"{prefix}_{sf}"))

    paged = len(buttons) > 30

    if paged:
        half = len(buttons) // 2
        buttons = buttons[:half] if page == 1 else buttons[half:]

    rows = split_list(buttons)

    if paged:
        label, target = (" >> ", "bk.p:2") if page == 1 else (" << ", "bk.p:1")
        rows.append([InlineKeyboardButton(label, callback_data=target)])

    footer = [
        InlineKeyboardButton("♞ All Search ♞", callback_data="plugin_all"),
        InlineKeyboardButton("🔥 Close 🔥", callback_data="kclose")
    ]
    rows.append(footer)

    return InlineKeyboardMarkup(rows)


def _parse_channel(value: str) -> int | str:
    try:
        return int(value)
    except (ValueError, TypeError):
        return value


async def _log(client, text: str) -> None:
    await retry_on_flood(client.send_message)(Vars.LOG_CHANNEL, text)


async def _invite_link(client, info: tuple) -> str:

    if len(info) > 2:
        return info[2]

    channel = _parse_channel(info[1])

    if isinstance(channel, str):
        return f"https://telegram.me/{channel.strip()}"

    if channel not in _invite_cache:
        _invite_cache[channel] = await client.export_chat_invite_link(channel)

    return _invite_cache[channel]


async def check_fsb(client, message) -> tuple[list[InlineKeyboardButton], list]:
    user_id = message.from_user.id

    async def check(info: tuple) -> InlineKeyboardButton | None:
        channel = _parse_channel(info[1])

        try:
            await client.get_chat_member(channel, user_id)
        except pyrogram.errors.UserNotParticipant:
            link = await _invite_link(client, info)
            return InlineKeyboardButton(info[0], url=link)
        except (pyrogram.errors.UsernameNotOccupied, pyrogram.errors.ChatAdminRequired) as e:
            await _log(client, f"Channel issue: {channel} - {type(e).__name__}")
        except (pyrogram.ContinuePropagation, pyrogram.StopPropagation):
            raise
        except Exception as e:
            await _log(client, f"Force Subscribe error: {e} at {channel}")

        return None

    # All channels are checked concurrently; gather keeps the original order
    results = await asyncio.gather(*map(check, client.FSB))

    return [button for button in results if button], []


def _chapter_priority(chap: dict) -> int:
    return _PREFERRED_PRIORITY.get(str(chap.get("group_name", "")).lower(), _NO_PRIORITY)


def select_preferred_chapters(chapters_raw: list[dict]) -> list[dict]:
    """Pick one chapter per number, preferring the scanlators listed above."""
    groups: dict[str, list[dict]] = {}

    for chap in chapters_raw:
        chap_num = get_episode_number(chap.get("title", ""))

        if chap_num is None or chap_num == 0:
            continue

        groups.setdefault(str(chap_num), []).append(chap)

    # min() returns the first item on ties, and group[0] when nobody is preferred
    selected = [(float(num), min(group, key=_chapter_priority)) for num, group in groups.items()]
    selected.sort(key=lambda item: item[0])

    return [chap for _, chap in selected]

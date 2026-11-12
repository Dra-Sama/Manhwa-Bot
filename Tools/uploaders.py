# Code By @V_Sbotmaker (on Telegram)
from typing import Tuple, Optional, Any
from .db import database, get_episode_number, clean_text_
import re
from bot import DEFAULT_SETTINGS, Vars, Bot
from pyrogram.types import Chat, Message, InlineKeyboardButton, InlineKeyboardMarkup
from .base import TTLCache, retry_on_flood
from loguru import logger
import asyncio

from pyrogram.enums import ButtonStyle


channel_info_cache = TTLCache(
    default_timeout=7200,  # 2 hours
    cleanup_interval=60    # Clean every minute to free memory quickly
)


_target_auto_private_cache = TTLCache(
    default_timeout=20,    
    cleanup_interval=10,
)
_PRIVATE_CACHE_KEY = "global_target_auto"


async def get_chat(channel_id: int | str) -> Optional[Chat]:
    try:
        channel_id = int(channel_id)

        if channel_id not in channel_info_cache:
            channel_info_cache[channel_id] = await retry_on_flood(Bot.get_chat)(channel_id)

        return channel_info_cache[channel_id]
    except Exception as er:
        logger.error(f"Error getting chat {channel_id}: {er}")

    return None


async def get_invite_link(channel_id: int, request: bool = False) -> Optional[str]:
    if i := await database.get_invite_link(channel_id):
        return i

    try:
        if not request:
            chat = await get_chat(channel_id)
            if i := getattr(chat, 'invite_link', None):
                await database.update_invite_link(channel_id, i)
                return i

        invite_link = await retry_on_flood(Bot.create_chat_invite_link)(
            channel_id, creates_join_request=request,
        )

        if i := getattr(invite_link, 'invite_link', None):
            await database.update_invite_link(channel_id, i)
            return i

    except Exception as er:
        logger.error(f"Error getting invite link for {channel_id}: {er}")

    return None


# ============================================
#  constants
# ============================================
_CONVERT_REPLACEMENTS = {
    "||": "&#124;&#124;",
    "|": "&#124;",
}

_URL_PATTERN = r'https?://[^\s<>"\'\)]+'
_TAG_LINK_RE = re.compile(r'<([^>]+)>\s*(' + _URL_PATTERN + r')')

_SKIP_TAGS = frozenset({
    "b", "i", "strong", "em", "u", "del", "strike", "spoiler",
    "emoji", "code", "pre", "blockquote", "tg-spoiler",
    "blockquote expandable", "||", "|", "/"
})


def convert_format(text):
    text = str(text)
    for key, value in _CONVERT_REPLACEMENTS.items():
        text = text.replace(key, value)

    lines = text.strip().split('\n')
    converted_lines = []

    for line in lines:
        try:
            match = _TAG_LINK_RE.search(line)

            if match:
                text_inside = match.group(1).strip()

                if text_inside.lower() in _SKIP_TAGS:
                    converted_lines.append(line)
                    continue

                link = match.group(2)

                if ' ' in text_inside or len(text_inside) > 20:
                    new_line = _TAG_LINK_RE.sub(f"<a href='{link}'>{text_inside}</a>", line)
                    converted_lines.append(new_line)
                else:
                    converted_lines.append(line)
            else:
                converted_lines.append(line)

        except Exception:
            converted_lines.append(line)
            continue

    return '\n'.join(converted_lines)


# ============================================
# Inline Button
# ============================================
"""
Params =>
  ➥ manga_title        : Manga Name
  ➥ chapter_num        : Chapter Number
  ➥ channel_title      : Channel Title
  ➥ channel_link       : To Redirect to Channel
  ➥ read_link          : To Redirect to Read Link
  ➥ channel_req_link   : To Redirect to Channel with request
  ➥  -                 : To Seperate Button Text and Link
  ➥  |                 : To Seperate Buttons
  ➥  &&                : To Seperate Buttons
  ➥ #r                 : Red Color to Buttons   (DANGER)
  ➥ #b                 : Blue Color to Buttons  (PRIMARY)
  ➥ #g                 : Green Color to Buttons (SUCCESS)

example:
  #r {manga_title} - {read_link} | #b {channel_title} - {channel_link}
  Next Line Button Text - http://www.example3.com/
"""

_BUTTON_COLOR_MAP = {
    "#r": ButtonStyle.DANGER,   # Red
    "#b": ButtonStyle.PRIMARY,  # Blue
    "#g": ButtonStyle.SUCCESS,  # Green
}


def convert_button_format(text: str) -> Optional[InlineKeyboardMarkup]:
    return_button = []
    lines = str(text).strip().split("\n")

    def parse_button(button_part: str):
        button_part = button_part.strip()
        if "-" not in button_part:
            return None

        style = None
        lowered = button_part.lower()
        for prefix, btn_style in _BUTTON_COLOR_MAP.items():
            if lowered.startswith(prefix) and (
                len(button_part) == len(prefix)
                or button_part[len(prefix)].isspace()
            ):
                style = btn_style
                button_part = button_part[len(prefix):].strip()
                break

        parts = button_part.split("-", 1)
        if len(parts) != 2:
            return None

        button_text = parts[0].strip()
        button_url = parts[1].strip()

        if not (button_text and button_url and button_url.startswith("http")):
            return None

        if style:
            return InlineKeyboardButton(button_text, url=button_url, style=style)

        return InlineKeyboardButton(button_text, url=button_url)

    for line in lines:
        if not line.strip():
            continue

        line_button = []
        if "|" in line:
            buttons = line.split("|")
        elif "&&" in line:
            buttons = line.split("&&")
        else:
            buttons = [line]

        for button_part in buttons:
            btn = parse_button(button_part)
            if btn:
                line_button.append(btn)

        if line_button:
            return_button.append(line_button)

    return InlineKeyboardMarkup(return_button) if return_button else None


def split_channel_name(channel_name: str):
    """Split channel name by various separators and clean each part"""
    separators = ["||", "|", "/"]

    for sep in separators:
        if sep in channel_name:
            parts = channel_name.split(sep)
            return [clean_text_(part.strip().lower()) for part in parts]

    return [clean_text_(channel_name.strip().lower())]


async def search_channel_photo(
    channel_info,
    last_id: int,
    BATCH_SIZE: int = 100,
):
    pin = getattr(channel_info, 'pinned_message', None)
    if pin and getattr(pin, 'photo', None):
        return pin.photo.file_id

    try:
        last_id = int(last_id)
        if last_id < 1:
            return None
    except Exception:
        return None

    start = 1
    while start <= last_id:
        end = min(start + BATCH_SIZE - 1, last_id)

        try:
            msgs = await retry_on_flood(Bot.get_messages)(
                channel_info.id,
                list(range(start, end + 1))
            )

            if isinstance(msgs, list):
                for m in msgs:
                    if m and m.photo:
                        return m.photo.file_id
            elif msgs and msgs.photo:
                return msgs.photo.file_id

        except Exception:
            pass

        start = end + 1

    return None


async def update_notify(
    post_info, user_id,
    manga_title, episode_number,
    channel_info: Chat
) -> None:
    user_id = str(user_id)
    uts = await database.get_settings(user_id)
    if not uts:
        return None

    update_channel = uts.get('update_c', None)
    update_text    = uts.get('update_t', None)
    update_sticker = uts.get('update_s', None)
    update_button  = uts.get('update_b', None)

    if not update_channel and Vars.IS_PRIVATE:
        update_channel = DEFAULT_SETTINGS.get('update_c', None)

    if not update_text and Vars.IS_PRIVATE:
        update_text    = DEFAULT_SETTINGS.get('update_t', None)
        update_sticker = DEFAULT_SETTINGS.get('update_s', None)
        update_button  = DEFAULT_SETTINGS.get('update_b', None)

    post_info = post_info[-1] if isinstance(post_info, list) else post_info

    if not update_channel or not update_text:
        await database.ensure_user(user_id)
        return

    try:
        """
        ➥ manga_title        : Manga Name
        ➥ chapter_num        : Chapter Number
        ➥ channel_title      : Channel Title
        ➥ channel_link       : To Redirect to Channel
        ➥ read_link          : To Redirect to Read Link
        ➥ channel_req_link   : To Redirect to Channel with request
        """

        update_text_str   = str(update_text)
        update_button_str = str(update_button) if update_button else ""
        request           = uts.get('request')
        needs_invite = any(
            ph in update_text_str or ph in update_button_str
            for ph in ("{channel_link}", "{channel_req_link}")
        )
        invite_link = (
            await get_invite_link(channel_info.id, request=True)
            if needs_invite or request else None
        )

        replacements = {
            "{manga_title}": manga_title,
            "{chapter_num}": str(episode_number),
            "{channel_title}": channel_info.title,
            "{channel_link}": invite_link or "",
            "{read_link}": getattr(post_info, 'link', ''),
            '{channel_req_link}': invite_link or "",
        }

        update_text, update_button = update_text_str, update_button_str
        for key, value in replacements.items():
            update_text = update_text.replace(key, value)

        if update_button:
            for key, value in replacements.items():
                update_button = update_button.replace(key, value)

        update_text   = convert_format(update_text)
        update_button = convert_button_format(update_button)

    except Exception as er:
        logger.exception(f"Error converting update text: {er}")
        return

    try:
        update_channel = int(update_channel)
    except Exception:
        pass

    try:
        message_list = await _get_recent_messages(channel_info.id, 40)

        for xcheck in message_list:
            try:
                if xcheck.text == update_text:
                    return

                elif xcheck.caption == update_text:
                    return

            except Exception:
                continue

    except Exception as e:
        logger.exception(f"Error checking messages: {e}")

    target_sticker = uts.get("target_s", None)

    if target_sticker:
        await retry_on_flood(Bot.send_sticker)(channel_info.id, target_sticker)

    post_photo = await search_channel_photo(channel_info, post_info.id)

    if post_photo:
        await retry_on_flood(Bot.send_photo)(
            update_channel, post_photo,
            caption=update_text,
            reply_markup=update_button,
        )

    else:
        await retry_on_flood(Bot.send_message)(
            update_channel, update_text,
            reply_markup=update_button,
        )

    if update_sticker:
        await retry_on_flood(Bot.send_sticker)(update_channel, update_sticker)


async def get_target_auto_channel(user_id: Optional[str] = None) -> Tuple[list, list]:
    if Vars.IS_PRIVATE is True:
        if _PRIVATE_CACHE_KEY in _target_auto_private_cache:
            return _target_auto_private_cache[_PRIVATE_CACHE_KEY]

        target_channel_ = []
        update_channel_ = []

        async for user_info in database.users.find(
            {}, {"target_channels": 1, "auto_channels": 1}
        ):
            target_channel_.extend(user_info.get('target_channels', []) or [])
            update_channel_.extend(user_info.get('auto_channels', []) or [])

        result = (target_channel_, update_channel_)
        _target_auto_private_cache[_PRIVATE_CACHE_KEY] = result
        return result

    target_channel_ = await database.get_target_channel(user_id)
    update_channel_ = await database.get_auto_channel(user_id)

    if not isinstance(target_channel_, list):
        target_channel_ = [target_channel_]

    if not isinstance(update_channel_, list):
        update_channel_ = [update_channel_]

    return target_channel_, update_channel_


async def _get_recent_messages(channel_id: int, count: int) -> list:
    """Get recent messages from a channel efficiently"""
    
    msg_id = await database.get_db_channel_msg(channel_id)
    try:
        if not isinstance(msg_id, int):
            await asyncio.sleep(2)
            test_msg = await retry_on_flood(Bot.send_message)(channel_id, "...")
            msg_id = test_msg.id

            await retry_on_flood(test_msg.delete)()
            await database.update_db_chanel_msg(channel_id, msg_id)

        logger.debug(f"Getting recent messages from channel {channel_id} with msg_id {msg_id}")

        
        lower = max(1, msg_id - count)
        upper = msg_id + count
        messages_ids = list(range(lower, upper))

        messages = await retry_on_flood(Bot.get_messages)(
            chat_id=channel_id, message_ids=messages_ids
        )

        if not isinstance(messages, list):
            messages = [messages]

        new_messages = [msg for msg in messages if getattr(msg, 'empty', None) is not True]

        return new_messages

    except ValueError:
        return []

    except Exception as e:
        logger.exception(f"Failed to get recent messages: {e}")
        return []


async def _ensure_channels_registered(channels: set) -> None:
    if not channels:
        return

    existing = await database.channels.find(
        {"_id": {"$in": list(channels)}}, {"_id": 1}
    ).to_list(length=None)
    
    existing_ids = {c["_id"] for c in existing}
    missing = channels - existing_ids

    for channel in missing:
        chat = await get_chat(channel)
        if not chat:
            continue

        await database.add_db_channel(
            channel_id=chat.id,
            channel_title=split_channel_name(chat.title),
        )


async def loads_in_db() -> None:
    ' Run when program start '
    t, a = await get_target_auto_channel()
    if not t and not a:
        return

    channels = set(t + a)
    await _ensure_channels_registered(channels)


async def loads_channels_in_db(
    user_id: Optional[str] = None,
    channels_pair: Optional[Tuple[list, list]] = None,
) -> Tuple[list, list]:
    if channels_pair is None:
        channels_pair = await get_target_auto_channel(user_id)

    t, a = channels_pair

    try:
        channels = set(t + a)
        await _ensure_channels_registered(channels)
    except Exception as er:
        logger.error(f"Error loading channels in DB: {er}")

    return channels_pair


class Uploader:
    __slots__ = ()

    @staticmethod
    def search_channel(channel_list: list[int], search_list: list[int]) -> Optional[int]:
        search_set = set(search_list)
        for channel_id in channel_list:
            if channel_id in search_set:
                return channel_id
        return None

    @staticmethod
    async def copy_to_matched(
        matched_channel: int, doc_channel_id: int,
        doc_message_id: int,
        client=None,                      # optional per-user bot client
    ) -> Message:
        # Use per-user client when provided, otherwise main bot
        _bot = client or Bot
        try:
            copied = await retry_on_flood(_bot.copy_media_group)(
                matched_channel,
                doc_channel_id,
                doc_message_id
            )
        except Exception:
            copied = await retry_on_flood(_bot.copy_message)(
                matched_channel,
                doc_channel_id,
                doc_message_id
            )

        return copied

    async def upload_to_targets_channels(
        self, docs: Message,
        original_ep_num: str, search_name: str,
        user_id: str,
        client: Optional[Any] = None,
    ) -> None:
        user_id = str(user_id)
        search_term = clean_text_(str(search_name).lower().strip())

        # Also build a caption-based search term (separate from filename)
        raw_caption = getattr(docs, 'caption', None) or ''
        caption_term = clean_text_(
            str(raw_caption).lower().strip().replace(str(original_ep_num), '')
        ).strip() if raw_caption else ''

        try:
            channels_pair = await get_target_auto_channel(user_id)
            target_channels, auto_channels = await loads_channels_in_db(
                user_id, channels_pair=channels_pair
            )

            # Search by filename-derived term
            found_channels = await database.search_db_channel(search_term)
            found_channel_ids = [c["_id"] for c in found_channels] if found_channels else []

            # Search by caption term (if different from filename term and non-empty)
            if caption_term and caption_term != search_term:
                caption_channels = await database.search_db_channel(caption_term)
                if caption_channels:
                    for c in caption_channels:
                        if c["_id"] not in found_channel_ids:
                            found_channel_ids.append(c["_id"])

            if not found_channel_ids:
                return

            all_user_channels = set(target_channels + auto_channels)

            target_channels_match = [
                c for c in found_channel_ids
                if c in all_user_channels
            ]

            if not target_channels_match:
                return

            channel_id = target_channels_match[0]

            # Duplicate check
            file_name = getattr(docs.document, 'file_name', None) if docs.document else None
            messages = await _get_recent_messages(channel_id, 40)

            # Duplicate check
            if self.checking_file_name_in(
                messages=messages, file_name=file_name,
                episode_str=original_ep_num
            ):
                return

            if raw_caption and self.checking_file_name_in(
                messages=messages, file_name=raw_caption,
                episode_str=original_ep_num
            ):
                return

            # ── Route upload through user's own bot client if available ──────
            user_client = client
            if user_client is None and channel_id in auto_channels:
                try:
                    from Tools.user_clients import user_client_manager  # noqa: PLC0415
                    user_client = await user_client_manager.get_client(user_id)
                except Exception as e:
                    logger.warning(f"[Uploader] Could not get user client for {user_id}: {e}")

            post_info = await self.copy_to_matched(
                channel_id, docs.chat.id, docs.id,
                client=user_client,
            )

            if not post_info:
                return

            if channel_id in auto_channels:
                channel_info = await get_chat(channel_id)
                await update_notify(
                    post_info=post_info, user_id=user_id,
                    manga_title=search_name, episode_number=original_ep_num,
                    channel_info=channel_info
                )

        except Exception as er:
            logger.exception(f"Error in upload_to_targets_channels: {er}")

        return


    @staticmethod
    def checking_file_name_in(
        messages: list[Message],
        file_name: Optional[str],
        episode_str: str,
    ) -> bool:
        if not file_name:
            file_name = None

        for msg in messages:
            document = getattr(msg, "document", None)
            if not document:
                continue

            doc_name = getattr(document, "file_name", "")
            caption_name = getattr(msg, "caption", "")
            doc_num = get_episode_number(doc_name)

            if file_name:
                s_d_c: tuple = (str(doc_name), str(caption_name), str(doc_num))
                if any(file_name in x for x in s_d_c):
                    return True

                if doc_name == file_name:
                    return True

            if episode_str and episode_str in doc_name:
                return True

            if doc_num and doc_num == episode_str:
                return True

        return False

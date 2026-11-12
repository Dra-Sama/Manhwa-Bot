# Code By @V_Sbotmaker (on Telegram)
"""
Database schema for manga tracking bot
_id: user_id
subs: {
  "ck": [
    { "url": "url1", "title": "title1", "lastest_chapter": "1", },
    { "url": "url2", "title": "title2", "lastest_chapter": "2", },
    ..............
  ],
  "as": [
    { "url": "url1", "title": "title1", "lastest_chapter": "1", },
    { "url": "url2", "title": "title2", "lastest_chapter": "2", },
    ..............
  ],
  ................
}
setting: {
  "file_name": "",
  "caption": "",
  ................
}
target_channels: []
auto_channels: []

for channels :

_id: -100
channel_title: ['Solo']
channel_msg: 01
invite_link: str
"""

import time
import re
from typing import Optional, Dict, List, Any, AsyncGenerator, Union
from functools import wraps

from loguru import logger
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError, DuplicateKeyError

from bot import Vars
from operator import itemgetter
from pyrogram.types import Message
from curl_cffi import requests
import tldextract
from asyncio import to_thread


slugs_sites = ("https://asurascans", )



def get_slugs(url: str) -> Optional[str]:
    """Extract a normalized slug from a manga URL for site-specific sources."""
    try:
        if not url:
            return None

        parts = url.split("/")[-1]
        if not parts:
            return None

        if url.startswith("https://asurascans"):
            result = "-".join(parts.split("-")[:-1])
            return result or None

        if url.startswith("https://comix.to/"):
            result = "-".join(parts.split("-")[1:])
            return result or None

        return parts
    except Exception:
        return None


def async_slogs(func):
    """Async decorator for error logging."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except PyMongoError as e:
            logger.error(f"MongoDB error in {func.__name__}: {e}")
            return None
        except Exception as err:
            logger.exception(f"Unexpected error in {func.__name__}: {err}")
            return None

    return wrapper



_EPISODE_PATTERNS = [
    (r"Vol(?:ume)?\.?\s*(\d+)\s+Chapter\s+(\d+(?:\.\d+)?)", 2),
    (r"Ch(?:apter)?\.?\s*(\d+)\s*[-\u2013\u2014]\s*(\d+(?:\.\d+)?)", 2),
    (r"Vol[.\- ]?\d+[.\- ]?Ch(?:apter)?[.\- ]?(\d+(?:\.\d+)?)", 1),
    (r"V\d+[.\- ]?C[.\- ]?(\d+(?:\.\d+)?)", 1),
    (r"Chapter\s+(\d+(?:\.\d+)?)", 1),
    (r"Ep(?:isode)?\.?\s*(\d+(?:\.\d+)?)", 1),
    (r"\[Ch(?:apter)?[.\- ]?(\d+(?:\.\d+)?)\]", 1),
    (r"\[C[.\- ]?(\d+(?:\.\d+)?)\]", 1),
    (r"\bChap(?:ter)?[.\- ]?(\d+(?:\.\d+)?)\b", 1),
    (r"\bCh(?:apter)?[.\- ]?(\d+(?:\.\d+)?)\b", 1),
    (r"\bC[.\- ]?(\d+(?:\.\d+)?)\b", 1),
    (r"(?<!\d)(\d{1,4}(?:\.\d+)?)(?!\d)", 1),
]


def get_episode_number(text: str) -> Optional[str]:
    """Extract episode/chapter number from text."""
    if not text:
        return None

    text = str(text).strip()

    for pattern, group in _EPISODE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if match.lastindex and match.lastindex >= group:
                return match.group(group)
            return match.group(1)

    return None


def get_effective_user_id(user_id: int | Message | str) -> str:
    """Returns a shared ID for admins if IS_PRIVATE is True."""
    if isinstance(user_id, Message):
        try:
            user_id = user_id.id
        except Exception:
            user_id = user_id.from_user.id

    return str(user_id)


text_to_remove = [
    ".pdf", ".cbz", "chapter", "ch-", "ch", ":", "꞉",
    "!", "⌯", "⇉", "$", "%", "^", "~", "+",
    "•", "||", "-", ",", "manga", "manhwa",
    "manhua", "pornhwa",
]


def get_domain(url: str) -> str:
    e = tldextract.extract(url)
    return f"{e.domain}.{e.suffix}" if e.suffix else e.domain

def clean_text_(text: str) -> str:
    """Clean and normalize text by removing mentions, brackets, and unwanted words."""
    text = text.lower()
    text = re.sub(r'@\w+|[\[\{\(].*?[\]\}\)]', '', text)

    if text_to_remove:
        text = str(text).strip()
        for word in text_to_remove:
            text = text.replace(word, '')

    return text.strip()


class MangaDB:
    """A class to manage manga data in the database."""

    __slots__ = ("users", "acollection", "_db", "channels", "sources_health")

    def __init__(self):
        """Initialize database connections."""

        client = AsyncMongoClient(
            Vars.DB_URL,
            maxPoolSize=20,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )

        self._db             = client[Vars.DB_NAME]
        self.users           = self._db.users
        self.acollection     = self._db.premium
        self.channels        = self._db.channels
        self.sources_health  = self._db.sources_health

    # ========================================================
    # Link (using request to get new link and update it at all )
    # ========================================================
    def fetch_new_link(self, link: str) -> Optional[str]:
        """Fetch a new link for a manga from the source."""
        try:
            headers = {
                "Host": get_domain(link),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/58.0.3029.110 Safari/537.3"


            }
            response = requests.get(
                link, headers=headers, allow_redirects=True, timeout=60)
            if response.url != link:
                return response.url

            return None
        except Exception as e:
            logger.error(f"Error fetching new link for {link}: {e}")
            return None

    @async_slogs
    async def get_links(self) -> list:
        """
        Get all manga links from the database that belong to slug-based sites.

        Returns a list of (user_id, web_key, url) tuples so update_link()
        can build a correct, targeted Mongo update (subs is a dict of arrays
        keyed by web short-name, e.g. "ck"/"as" -- not a flat array, so we
        can't $elemMatch across the whole subs object).
        """
        cursor = self.users.find(
            {"subs": {"$ne": {}}},
            {"_id": 1, "subs": 1}
        )
        links = []
        async for user_data in cursor:
            user_id = user_data.get("_id")
            subs = user_data.get("subs", {})
            for web_key, web_subs in subs.items():
                if not isinstance(web_subs, list):
                    # Data corruption: subs.<web_key> should always be a
                    # list of dicts. If it's e.g. a bare string, iterating
                    # it yields individual characters, and any $pull against
                    # it later (delete_sub, etc.) throws "Cannot apply
                    # $pull to a non-array value". Heal it now via $set
                    # (which works on any field type) rather than leaving
                    # it broken for every future read/write.
                    logger.warning(
                        f"Corrupted subs field for user {user_id}, web "
                        f"'{web_key}' (type={type(web_subs).__name__}, "
                        f"value={web_subs!r}); resetting to []"
                    )
                    await self.users.update_one(
                        {"_id": user_id},
                        {"$set": {f"subs.{web_key}": []}},
                    )
                    continue

                valid_subs = [s for s in web_subs if isinstance(s, dict)]
                if len(valid_subs) != len(web_subs):
                    logger.info(
                        f"Dropping {len(web_subs) - len(valid_subs)} invalid "
                        f"sub entr(y/ies) for user {user_id}, web '{web_key}'"
                    )
                    # Replace with only the valid entries -- never wipe the
                    # whole array, or every good subscription gets lost too.
                    await self.users.update_one(
                        {"_id": user_id},
                        {"$set": {f"subs.{web_key}": valid_subs}},
                    )

                for sub in valid_subs:
                    url = sub.get("url")
                    if not url:
                        continue

                    if any(url.startswith(i) for i in slugs_sites):
                        links.append((user_id, web_key, url))

        return links

    async def auto_update_links(self):
        """Automatically update links for all manga in the database."""
        links = await self.get_links()
        logger.info(f"Found {len(links)} links to check for updates.")
        for user_id, web_key, link in links:
            logger.info(f"Checking link: {link}")
            await self.update_link(user_id, web_key, link)

    @async_slogs
    async def update_link(
        self,
        user_id: Union[str, int],
        web_key: str,
        old_link: str,
        new_link: Optional[str] = None,
    ) -> Optional[str]:
        """Update the link for a manga in the database.

        Needs user_id + web_key because `subs` is a dict-of-arrays
        (subs.<web_key> = [...]), so Mongo's positional `$` operator has to be
        scoped to the exact array field -- `{"subs": {"$elemMatch": ...}}`
        can never match since "subs" itself isn't an array.

        If `new_link` is already known (e.g. the caller already resolved it
        via fetch_new_link), pass it in to skip a redundant network request.
        Returns the new link on success, or None.
        """
        try:
            user_id = str(user_id)
            if new_link is None:
                new_link = await to_thread(self.fetch_new_link, old_link)
            if not new_link:
                logger.warning(f"No new link found for {old_link}")
                return None

            result = await self.users.update_one(
                {"_id": user_id, f"subs.{web_key}.url": old_link},
                {"$set": {f"subs.{web_key}.$.url": new_link}},
            )

            if result.modified_count:
                logger.info(f"Updated link from {old_link} to {new_link}")
                return new_link
            else:
                logger.warning(
                    f"No document matched for user {user_id}, web '{web_key}', url {old_link}"
                )
                return None
        except Exception as e:
            logger.error(f"Error updating link for {old_link}: {e}")
            return None

    # =========================================================
    # DB Channels
    # =========================================================

    @async_slogs
    async def add_db_channel(
        self,
        channel_id: int,
        channel_title: list,
        msg_id: Optional[int] = None,
        invite_link: Optional[str] = None
    ) -> bool:
        channel_id = int(channel_id)

        if not isinstance(channel_title, list):
            channel_title = [channel_title]

        channel_titles = [
            clean_text_(str(title))
            for title in channel_title
        ]

        channel_data = {
            "_id": channel_id,
            "channel_title": channel_titles,
            "channel_msg": msg_id,
            "invite_link": invite_link,
        }

        try:
            r = await self.channels.insert_one(channel_data)
            return bool(r.inserted_id)
        except DuplicateKeyError:
            logger.debug(f"Channel {channel_id} already exists")
            return False

    @async_slogs
    async def delete_db_channel(self, channel_id: int) -> bool:
        channel_id = int(channel_id)
        r = await self.channels.delete_one({"_id": channel_id})
        return r.deleted_count > 0

    @async_slogs
    async def check_db_channel(self, channel_id: int) -> bool:
        channel_id = int(channel_id)
        channel_data = await self.channels.find_one({"_id": channel_id}, {"_id": 1})
        return bool(channel_data)

    @async_slogs
    async def get_db_channel(self, channel_id: int) -> Optional[Dict]:
        channel_id = int(channel_id)
        return await self.channels.find_one({"_id": channel_id})

    @async_slogs
    async def search_db_channel(
        self,
        channel_title: str,
    ) -> Optional[list]:
        """Search channel by title and return all found channels."""
        channel_title = clean_text_(str(channel_title))

        cursor = self.channels.find(
            {
                "channel_title": {
                    "$regex": f"^{re.escape(channel_title)}",
                    "$options": "i"
                },
            }
        )

        return await cursor.to_list(length=None)

    @async_slogs
    async def update_db_channel_title(
        self,
        channel_id: int,
        channel_title: list,
    ) -> None:
        channel_id = int(channel_id)
        channel_titles = [clean_text_(str(title)) for title in channel_title]

        await self.channels.update_one(
            {"_id": channel_id},
            {"$set": {"channel_title": channel_titles}},
        )

    @async_slogs
    async def get_db_channels(self) -> list:
        channel_data = await self.channels.find({}).to_list(length=None)
        return channel_data

    @async_slogs
    async def update_db_chanel_msg(self, channel_id: int, msg_id: int) -> None:
        channel_id = int(channel_id)
        msg_id = int(msg_id)
        await self.channels.update_one(
            {"_id": channel_id}, {"$set": {"channel_msg": msg_id}}
        )

    @async_slogs
    async def get_db_channel_msg(self, channel_id: int) -> Optional[int]:
        channel_id = int(channel_id)
        channel_data = await self.channels.find_one({"_id": channel_id}, {"channel_msg": 1})
        return channel_data.get("channel_msg") if channel_data else None

    @async_slogs
    async def update_invite_link(self, channel_id: int, invite_link: str) -> None:
        channel_id = int(channel_id)
        await self.channels.update_one(
            {'_id': channel_id},
            {'$set': {'invite_link': invite_link}}
        )

    @async_slogs
    async def get_invite_link(self, channel_id: int) -> Optional[str]:
        channel_id = int(channel_id)
        i = await self.channels.find_one({'_id': channel_id}, {'invite_link': 1})
        return i.get('invite_link') if i else None

    # =========================================================
    # Users
    # =========================================================

    @async_slogs
    async def ensure_user(self, user_id: Union[str, int]) -> bool:
        """Ensure user exists in database, create if not."""
        user_id = get_effective_user_id(user_id)

        user_data = await self.users.find_one({"_id": user_id}, {"_id": 1})
        if user_data:
            return True

        user_data = {
            "_id": user_id,
            "subs": {},
            "setting": {},
            "target_channels": [],
            "auto_channels": [],
        }

        try:
            await self.users.insert_one(user_data)
            logger.debug(f"Created new user: {user_id}")
            return True
        except DuplicateKeyError:
            return True
            
        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            return False

    @async_slogs
    async def get_users_data(self, user_id: Optional[Union[str, int]]):
        user_id = get_effective_user_id(user_id)
        return await self.users.find_one({"_id": user_id})

    async def get_users(
        self, user_id: Optional[Union[str, int]] = None
    ) -> AsyncGenerator[Dict, None]:
        """Get user(s) from database."""
        if user_id is not None:
            user_id = str(user_id)
            user_data = await self.users.find_one({"_id": user_id})
            if user_data:
                yield user_data
            return

        async for doc in self.users.find({}):
            if isinstance(doc, dict):
                yield doc

    @async_slogs
    async def delete_user(self, user_id: Union[str, int]) -> bool:
        """Delete a user, trying both the str and int forms of the id
        (older records may have been stored with either)."""
        candidate_ids = {str(user_id)}
        try:
            candidate_ids.add(int(user_id))
        except (ValueError, TypeError):
            pass

        for candidate in candidate_ids:
            delete_result = await self.users.delete_one({"_id": candidate})
            if delete_result.deleted_count > 0:
                logger.debug(f"Successfully deleted user: {candidate}")
                return True

        for candidate in candidate_ids:
            update_result = await self.users.update_one(
                {"_id": candidate}, {"$set": {"subs": {}, "setting": {}}}
            )
            if update_result.matched_count > 0:
                logger.info(f"User {candidate} not deleted, but data was cleared")
                return True

        logger.warning(f"User {user_id} not found for deletion")
        return False

    # =========================================================
    # Settings
    # =========================================================

    @async_slogs
    async def get_settings(self, user_id: Union[str, int]):
        """Get user settings."""
        user_id = str(user_id)
        user_data = await self.users.find_one({"_id": user_id}, {"setting": 1})
        return user_data.get("setting", {}) if user_data else {}

    @async_slogs
    async def get_value(self, user_id: Union[str, int], key: str):
        """Get specific setting value for user."""
        user_id = str(user_id)
        user_data = await self.users.find_one({"_id": user_id}, {f"setting.{key}": 1})
        return user_data.get("setting", {}).get(key, None) if user_data else None

    @async_slogs
    async def set_value(self, user_id: Union[str, int], key: str, value: Any):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id}, {"$set": {f"setting.{key}": value}}
        )

    @async_slogs
    async def delete_value(self, user_id: Union[str, int], key: str):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id}, {"$unset": {f"setting.{key}": ""}}
        )

    # =========================================================
    # Channels (generic — replaces 8 duplicated helpers)
    # =========================================================

    @async_slogs
    async def get_channels(self, user_id: Union[str, int], channel_type: str) -> list:
        user_id = str(user_id)
        user_data = await self.users.find_one({"_id": user_id}, {channel_type: 1})
        return user_data.get(channel_type, []) if user_data else []

    @async_slogs
    async def add_channel(
        self, user_id: Union[str, int], channel_type: str, channel_id: int
    ):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id}, {"$addToSet": {channel_type: channel_id}}
        )

    @async_slogs
    async def remove_channel(
        self, user_id: Union[str, int], channel_type: str, channel_id: int
    ):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id}, {"$pull": {channel_type: channel_id}}
        )

    @async_slogs
    async def erase_channel(self, user_id: Union[str, int], channel_type: str):
        user_id = str(user_id)
        await self.users.update_one({"_id": user_id}, {"$set": {channel_type: []}})

    async def get_target_channel(self, user_id):
        return await self.get_channels(user_id, "target_channels")

    async def get_auto_channel(self, user_id):
        return await self.get_channels(user_id, "auto_channels")

    async def add_target_channel(self, user_id, channel_id):
        return await self.add_channel(user_id, "target_channels", channel_id)

    async def add_auto_channel(self, user_id, channel_id):
        return await self.add_channel(user_id, "auto_channels", channel_id)

    async def remove_target_channel(self, user_id, channel_id):
        return await self.remove_channel(user_id, "target_channels", channel_id)

    async def remove_auto_channel(self, user_id, channel_id):
        return await self.remove_channel(user_id, "auto_channels", channel_id)

    async def erase_target_channel(self, user_id):
        return await self.erase_channel(user_id, "target_channels")

    async def erase_auto_channel(self, user_id):
        return await self.erase_channel(user_id, "auto_channels")

    @async_slogs
    async def check_dump(self, channel_id: Union[str, int]) -> Optional[str]:
        """Check if channel is configured as dump or auto channel for any user."""
        channel_id = int(channel_id)

        user_data = await self.users.find_one(
            {
                "$or": [
                    {"setting.dump": channel_id},
                    {"target_channels": channel_id},
                    {"auto_channels": channel_id},
                ]
            },
            {"_id": 1},
        )

        if user_data and user_data.get("_id"):
            return str(user_data["_id"])

        return None

    # =========================================================
    # Per-user Bot Token  (for auto-upload via user's own bot)
    # =========================================================

    @async_slogs
    async def get_bot_token(self, user_id: Union[str, int]) -> Optional[str]:
        """Return the stored (obfuscated) bot token for user, or None."""
        user_id = str(user_id)
        doc = await self.users.find_one({"_id": user_id}, {"setting.bot_token": 1})
        return (doc or {}).get("setting", {}).get("bot_token")

    @async_slogs
    async def set_bot_token(self, user_id: Union[str, int], token_enc: str) -> bool:
        """Store the obfuscated bot token for user."""
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {"setting.bot_token": token_enc}},
            upsert=True,
        )
        return True

    @async_slogs
    async def delete_bot_token(self, user_id: Union[str, int]) -> bool:
        """Remove stored bot token for user."""
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$unset": {"setting.bot_token": ""}},
        )
        return True

    @async_slogs
    async def mark_alert_sent(self, user_id: Union[str, int]) -> bool:
        """Mark that the migration alert has been sent to this user."""
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {"bot_token_alert_sent": True}},
        )
        return True

    async def get_users_needing_alert(self):
        """
        Yield user documents where:
          * user has at least one target or auto channel configured, AND
          * no bot_token stored yet, AND
          * migration alert hasn't been sent yet.
        """
        cursor = self.users.find(
            {
                "$and": [
                    {"bot_token_alert_sent": {"$ne": True}},
                    {"setting.bot_token": {"$exists": False}},
                    {"$or": [
                        {"target_channels": {"$exists": True, "$ne": []}},
                        {"auto_channels":   {"$exists": True, "$ne": []}},
                    ]},
                ]
            }
        )
        async for doc in cursor:
            yield doc



    @async_slogs
    async def add_sub(
        self,
        user_id: Union[str, int],
        rdata: Any,
        web: str,
        chapter: Optional[str] = None,
    ) -> bool:
        """Add subscription for user."""
        user_id = get_effective_user_id(user_id)

        if not await self.ensure_user(user_id):
            return False

        if hasattr(rdata, "load_to_dict"):
            rdata = rdata.load_to_dict()

        if not isinstance(rdata, dict):
            logger.error(f"Invalid rdata type: {type(rdata)}")
            return False

        if "manga_title" in rdata:
            rdata["title"] = rdata.pop("manga_title")

        if "manga_url" in rdata:
            rdata["url"] = rdata.pop("manga_url")

        if chapter and "lastest_chapter" not in rdata:
            rdata["lastest_chapter"] = chapter

        manga_url = rdata.get("url")
        if not manga_url:
            logger.error(f"add_sub called without a url for user {user_id}")
            return False
        manga_url = str(manga_url)
        rdata["url"] = manga_url

        if any(manga_url.startswith(i) for i in slugs_sites):
            slugs = get_slugs(manga_url)
            rdata["slugs"] = slugs

        result = await self.users.update_one(
            {
                "_id": user_id,
                f"subs.{web}.url": {"$ne": manga_url},
            },
            {"$push": {f"subs.{web}": rdata}},
        )

        return bool(result.modified_count)

    @async_slogs
    async def check_sub(
        self,
        UserID: Union[str, int],
        manga_url: Optional[str] = None,
        web: Optional[str] = None,
    ) -> bool:
        """Check if user has subscription."""
        UserID = str(UserID)

        if manga_url:
            original_url = manga_url

            # Slug-based sites (asurascans, comix.to) sometimes move behind a
            # redirect (domain change, CDN migration, etc). Resolve to the
            # live URL first so lookups aren't comparing against a stale
            # link, and opportunistically heal the stored subscription.
            if any(manga_url.startswith(i) for i in slugs_sites):
                try:
                    new_link = await to_thread(self.fetch_new_link, manga_url)
                except Exception as e:
                    logger.warning(
                        f"fetch_new_link failed for {manga_url}: {e}")
                    new_link = None

                if new_link and new_link != original_url:
                    logger.info(
                        f"Resolved redirected link: {original_url} -> {new_link}")
                    if web:
                        # Pass new_link through so update_link doesn't fetch again.
                        await self.update_link(UserID, web, original_url, new_link=new_link)
                    manga_url = new_link

            _, r = await self.find_through_url_slugs(UserID, manga_url)
            if not r and manga_url != original_url:
                # The resolved link's slug didn't match anything stored --
                # fall back to the original URL before giving up, in case
                # the DB still has the pre-redirect link/slug.
                _, r = await self.find_through_url_slugs(UserID, original_url)
            return bool(r)

        user_data = await self.users.find_one({"_id": UserID}, {"subs": 1})
        subs_data = user_data.get("subs", {}) if user_data else {}
        if not subs_data:
            return False

        if not web:
            return True

        return web in subs_data

    @async_slogs
    async def delete_sub(
        self,
        UserID: Union[str, int],
        manga_url: Optional[str] = None,
        web: Optional[str] = None,
    ) -> bool:
        """Delete subscription(s) for user."""
        UserID = str(UserID)

        if manga_url:
            user_id, rdata = await self.find_through_url_slugs(UserID, manga_url)
            if not rdata:
                return False

            from TG.storage import check_get_web
            web_obj = check_get_web(manga_url)
            if not web_obj:
                return False

            # $pull requires the target field to actually be an array --
            # if it's been corrupted into a string/other type, Mongo throws
            # "Cannot apply $pull to a non-array value". Check first and
            # heal instead of crashing.
            current = await self.users.find_one(
                {"_id": user_id}, {f"subs.{web_obj.sf}": 1}
            )
            field_value = (current or {}).get("subs", {}).get(web_obj.sf)
            if field_value is not None and not isinstance(field_value, list):
                logger.warning(
                    f"Corrupted subs field for user {user_id}, web "
                    f"'{web_obj.sf}' (type={type(field_value).__name__}); "
                    f"resetting to [] instead of $pull"
                )
                await self.users.update_one(
                    {"_id": user_id}, {"$set": {f"subs.{web_obj.sf}": []}}
                )
                return False

            if any(manga_url.startswith(i) for i in slugs_sites):
                update_data = {
                    "$pull": {f"subs.{web_obj.sf}": {"slugs": rdata.get("slugs")}}}
            else:
                update_data = {
                    "$pull": {f"subs.{web_obj.sf}": {"url": manga_url}}}

            result = await self.users.update_one({"_id": user_id}, update_data)
            return result.modified_count > 0

        if not await self.check_sub(UserID, web=web):
            return False

        if web:
            update_query = {"$unset": {f"subs.{web}": ""}}
        else:
            update_query = {"$set": {"subs": {}}}

        result = await self.users.update_one({"_id": UserID}, update_query)
        return result.modified_count > 0

    @async_slogs
    async def get_subs(
        self,
        UserID: Union[str, int],
        manga_url: Optional[str] = None,
        web: Optional[str] = None,
    ) -> Optional[Union[List, Dict]]:
        """Get user's subscriptions."""
        UserID = str(UserID)

        if manga_url:
            try:
                _, rdata = await self.find_through_url_slugs(UserID, manga_url=manga_url)
                return rdata
            except Exception:
                return None

        udata = await self.users.find_one({"_id": UserID}, {"subs": 1})
        udata = udata.get("subs", {}) if udata else {}

        if not udata:
            return None

        if not web:
            return [chapter_data for subs in udata.values() for chapter_data in subs]

        return udata.get(web, []) or None

    async def get_all_subs(self) -> AsyncGenerator:
        """Get all users with subscriptions."""
        async for user_data in self.users.find({"subs": {"$ne": {}}}):
            if user_data.get("subs"):
                yield user_data

    @async_slogs
    async def change_ls(
        self,
        user_id: Union[str, int],
        ls_num: Union[int, str],
        index_num: Optional[int] = None,
        manga_url: Optional[str] = None,
    ) -> bool:
        """Change latest chapter number for a subscription."""
        from TG.storage import check_get_web

        user_id = get_effective_user_id(user_id)

        manga_data = None

        if manga_url:
            manga_data = await self.get_subs(user_id, manga_url=manga_url)

        elif index_num is not None:
            subs = await self.get_subs(user_id)
            if not subs:
                logger.warning(f"No subscriptions found for user {user_id}")
                return False

            try:
                manga_data = subs[index_num]
            except IndexError:
                logger.error(
                    f"Index {index_num} out of range for user {user_id}")
                return False

        if not manga_data:
            logger.warning(
                f"Manga not found for user {user_id} (url: {manga_url}, index: {index_num})"
            )
            return False

        manga_data["lastest_chapter"] = ls_num
        url_to_match = manga_data["url"]

        web = check_get_web(url_to_match)
        web_sf = web.sf if web else "default"

        try:
            for web_name_sf in (web_sf, "default"):
                check_data = {"_id": user_id,
                              f"subs.{web_name_sf}.url": url_to_match}
                update_data = {"$set": {f"subs.{web_name_sf}.$": manga_data}}
                if await self.update_chapter(check_data, update_data):
                    return True

            logger.error(
                f"Failed to update subscription for user {user_id}, URL: {url_to_match}"
            )
            return False

        except Exception as e:
            logger.exception(f"Error in change_ls for user {user_id}: {e}")
            return False

    async def update_chapter(self, check_data: dict, update_data: dict) -> bool:
        """Update chapter information for a subscription."""
        try:
            result = await self.users.update_one(check_data, update_data)
            return result.modified_count > 0
        except Exception as er:
            logger.exception(f"Error updating chapter: {er}")
        return False

    # =========================================================
    # Slugs
    # =========================================================

    @async_slogs
    async def find_through_url_slugs(
        self,
        UserID: Union[str, int],
        manga_url: str,
    ) -> tuple:
        UserID = str(UserID)

        slugs = get_slugs(manga_url)
        use_slugs = bool(slugs) and any(manga_url.startswith(i)
                                        for i in slugs_sites)

        if not slugs:
            return None, None

        match_stage = (
            {"$match": {"subs_array.v.slugs": slugs}}
            if use_slugs
            else {"$match": {"subs_array.v.url": manga_url}}
        )

        pipeline = [
            {"$match": {"_id": UserID}},
            {"$project": {"subs_array": {"$objectToArray": "$subs"}}},
            {"$unwind": "$subs_array"},
            {"$unwind": "$subs_array.v"},
            match_stage,
            {
                "$project": {
                    "_id": 0,
                    "url":             "$subs_array.v.url",
                    "title":           "$subs_array.v.title",
                    "lastest_chapter": "$subs_array.v.lastest_chapter",
                    "slugs":           "$subs_array.v.slugs",
                }
            },
        ]

        try:
            results = await self.users.aggregate(pipeline)
            r = await results.to_list(length=1)
            if not r:
                return None, None

            doc = r[0]
            if use_slugs and not doc.get("slugs"):
                doc["slugs"] = slugs

            return UserID, doc

        except Exception as er:
            logger.exception(f"Error in find_through_url_slugs: {er}")
            return None, None

    async def match_through_url_slugs(
        self,
        UserID: Union[str, int],
        web_sf: str,
        manga_url: str,
        slugs: str,
    ) -> tuple:
        for web_sf_name in (web_sf, "default"):
            subs_data = await self.users.find_one(
                {"_id": UserID},
                {"_id": 0, f"subs.{web_sf_name}": 1},
            )

            if not subs_data:
                continue

            web_data = subs_data.get("subs", {}).get(web_sf_name, [])
            if not web_data:
                continue

            try:
                get_url = itemgetter("url")
                matches = [
                    manga_data
                    for manga_data in web_data
                    if (url := get_url(manga_data))
                    and (w_slug := get_slugs(url))
                    and w_slug == slugs
                ]

                rdata = matches[0] if matches else None
                return UserID, web_sf_name, rdata
            except Exception:
                return None, None, None

        return None, None, None

    async def update_through_slugs(
        self,
        user_id: Union[str, int],
        manga_url: str,
        filter_data: dict,
        web_sf: str,
    ) -> bool:
        userID = str(user_id)

        slug = get_slugs(manga_url)
        if not slug:
            return False

        logger.debug(f"Updating through slugs: {slug} [{web_sf}]")

        for web_sf_name in (web_sf, "default"):
            check_data = {"_id": userID, f"subs.{web_sf_name}.slugs": slug}
            update_data = {"$set": {f"subs.{web_sf_name}.$": filter_data}}
            if await self.update_chapter(check_data, update_data):
                return True

        user_id, web_sf, matches = await self.match_through_url_slugs(
            userID, web_sf=web_sf, manga_url=manga_url, slugs=slug
        )
        if not matches or not web_sf or not user_id:
            return False

        filter_data["slugs"] = slug

        check_data = {"_id": user_id, f"subs.{web_sf}.url": manga_url}
        update_data = {"$set": {f"subs.{web_sf}.$": filter_data}}

        return await self.update_chapter(check_data, update_data)

    @async_slogs
    async def save_latest_chapter(
        self, data: Dict, user_id: Union[str, int], web_sf: str
    ):
        """Update the latest chapter for subscribed manga."""
        try:
            if "url" not in data:
                logger.error("No URL provided in data")
                return False

            manga_url = str(data["url"])

            chapter_update: dict = {"lastest_chapter": data["lastest_chapter"]}
            if "slugs" in data:
                chapter_update["slugs"] = data["slugs"]

            if "title" in data:
                chapter_update["title"] = data["title"]

            userID = str(user_id)

            if any(manga_url.startswith(i) for i in slugs_sites):
                for web_sf_name in (web_sf, "default"):
                    await self.update_link(userID, web_sf_name, manga_url)
                # all manga url update to new


            for web_sf_name in (web_sf, "default"):
                check_data = {"_id": userID,
                              f"subs.{web_sf_name}.url": manga_url}
                update_data = {
                    "$set": {
                        f"subs.{web_sf_name}.$.lastest_chapter": chapter_update["lastest_chapter"]
                    }
                }
                # Same title-persistence fix as above for non-slug sites.
                if "title" in chapter_update:
                    update_data["$set"][f"subs.{web_sf_name}.$.title"] = chapter_update["title"]

                if await self.update_chapter(check_data, update_data):
                    return True

            logger.error(
                f"Failed to find subscription to update for user {user_id}, URL: {manga_url}"
            )
            return False

        except Exception as err:
            logger.exception(f"Error saving latest chapter: {err}")
        return False

    # =========================================================
    # Export / Import
    # =========================================================

    @async_slogs
    async def get_full_user_data(self, user_id: Union[str, int]) -> Dict:
        """Get full user data for export."""
        user_id = get_effective_user_id(user_id)
        user_data = await self.users.find_one(
            {"_id": user_id},
            {"subs": 1, "setting": 1, "target_channels": 1, "auto_channels": 1},
        )
        if not user_data:
            return {}

        return {
            "subs": user_data.get("subs", {}),
            "setting": user_data.get("setting", {}),
            "target_channels": user_data.get("target_channels", []),
            "auto_channels": user_data.get("auto_channels", []),
        }

    @async_slogs
    async def update_user_data(self, user_id: Union[str, int], data: Dict) -> bool:
        """Update user data from imported JSON."""
        user_id = get_effective_user_id(user_id)
        if not await self.ensure_user(user_id):
            return False

        update_query = {}
        subs_data = data.get("subs") or data.get("subscriptions")

        if subs_data:
            if isinstance(subs_data, list):
                formatted_subs: dict = {}
                for sub in subs_data:
                    web = sub.get("web") or "default"
                    if web not in formatted_subs:
                        formatted_subs[web] = []

                    mapped_sub = {
                        "url":            sub.get("url") or sub.get("manga_url"),
                        "title":          sub.get("title") or sub.get("manga_title"),
                        "lastest_chapter": sub.get("lastest_chapter"),
                    }
                    mapped_sub = {k: v for k,
                                  v in mapped_sub.items() if v is not None}
                    formatted_subs[web].append(mapped_sub)
                update_query["subs"] = formatted_subs
            else:
                update_query["subs"] = subs_data

        for key in ["target_channels", "auto_channels"]:
            if key in data:
                update_query[key] = data[key]

        if not update_query:
            logger.warning(
                f"No valid keys found in import data for user {user_id}")
            return False

        result = await self.users.update_one({"_id": user_id}, {"$set": update_query})
        return result.acknowledged

    # =========================================================
    # Premium
    # =========================================================

    def parse_duration(self, duration_str: str) -> int:
        """Parse duration string like '1 day', '1 month' into days."""
        try:
            match = re.search(
                r"(\d+)\s*([a-zA-Z]+)", str(duration_str).strip())
            if not match:
                return int(duration_str)

            value = int(match.group(1))
            unit = match.group(2).lower()

            if unit.startswith("day"):
                return value
            elif unit.startswith("week"):
                return value * 7
            elif unit.startswith("month"):
                return value * 30
            elif unit.startswith("year"):
                return value * 365
            else:
                return value
        except Exception:
            try:
                return int(duration_str)
            except Exception:
                return 0

    @async_slogs
    async def add_premium(
        self, user_id: Union[str, int], time_limit: Union[int, str]
    ) -> bool:
        """Add premium status to user."""
        user_id = str(user_id)

        time_limit_days = (
            self.parse_duration(time_limit) if isinstance(
                time_limit, str) else time_limit
        )

        expiration_timestamp = int(time.time()) + \
            (time_limit_days * 24 * 60 * 60)

        result = await self.acollection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "expiration_timestamp": expiration_timestamp,
                    "added_at": int(time.time()),
                }
            },
            upsert=True,
        )

        success = result.modified_count > 0 or result.upserted_id is not None
        if success:
            logger.info(f"Added/updated premium for user {user_id}")
        return success

    @async_slogs
    async def remove_premium(self, user_id: Union[str, int]) -> bool:
        """Remove premium status from user."""
        user_id = str(user_id)
        result = await self.acollection.delete_one({"_id": user_id})
        success = result.deleted_count > 0
        if success:
            logger.info(f"Removed premium for user {user_id}")
        return success

    @async_slogs
    async def remove_expired_users(self) -> int:
        """Remove expired premium users and return count removed."""
        current_timestamp = int(time.time())
        result = await self.acollection.delete_many(
            {"expiration_timestamp": {"$lt": current_timestamp}}
        )
        count = result.deleted_count
        if count > 0:
            logger.info(f"Removed {count} expired premium users")
        return count

    async def get_all_premium(self) -> AsyncGenerator:
        """Get all premium user IDs."""
        async for doc in self.acollection.find(
            {"expiration_timestamp": {"$gt": int(time.time())}}
        ):
            if doc and doc.get("_id"):
                yield str(doc["_id"]), doc

    @async_slogs
    async def premium_user(self, user_id: Union[str, int]) -> Optional[Dict]:
        """Check if user has active premium status."""
        user_id = str(user_id)
        return await self.acollection.find_one(
            {"_id": user_id, "expiration_timestamp": {"$gt": int(time.time())}}
        )

    async def is_authorized(self, user_id: Union[str, int]) -> bool:
        """Check if user is authorized (admin or premium)."""
        if not Vars.IS_PRIVATE:
            return True

        try:
            if int(user_id) in Vars.ADMINS:
                return True
        except (ValueError, TypeError):
            pass

        return bool(await self.premium_user(user_id))

    # =========================================================
    # Source Health & Preferences
    # =========================================================

    @async_slogs
    async def get_source_health(self, sf: str) -> Optional[Dict]:
        """Fetch health status for a specific source by short name."""
        return await self.sources_health.find_one({"_id": sf})

    @async_slogs
    async def get_all_sources_health(self) -> Dict[str, Dict]:
        """Fetch health status for all recorded sources."""
        docs = await self.sources_health.find({}).to_list(length=None)
        return {doc["_id"]: doc for doc in docs if isinstance(doc, dict) and "_id" in doc}

    @async_slogs
    async def auto_disable_source(
        self, sf: str, name: str, url: str = "", last_error: str = ""
    ) -> bool:
        """
        Automatically mark a source as auto_disabled after repeated retries fail.
        Returns True ONLY if status transitioned from enabled to auto_disabled (to send single notification).
        """
        existing = await self.sources_health.find_one({"_id": sf})
        if existing and existing.get("status") == "auto_disabled":
            return False

        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        await self.sources_health.update_one(
            {"_id": sf},
            {
                "$set": {
                    "name": name,
                    "url": url or "N/A",
                    "status": "auto_disabled",
                    "retry_count": 3,
                    "last_error": last_error or "Repeated failures",
                    "disabled_at": now_utc,
                    "notification_sent": True,
                }
            },
            upsert=True,
        )
        return True

    @async_slogs
    async def re_enable_source(self, sf: str) -> bool:
        """Manually re-enable an automatically or manually disabled source."""
        await self.sources_health.update_one(
            {"_id": sf},
            {
                "$set": {
                    "status": "enabled",
                    "retry_count": 0,
                    "last_error": None,
                    "notification_sent": False,
                }
            },
            upsert=True,
        )
        return True

    @async_slogs
    async def is_source_globally_enabled(self, sf: str) -> bool:
        """Check if source is globally enabled (not auto_disabled or manually_disabled)."""
        doc = await self.sources_health.find_one({"_id": sf}, {"status": 1})
        if doc and doc.get("status") in ("auto_disabled", "manually_disabled"):
            return False
        return True

    @async_slogs
    async def get_user_disabled_sources(self, user_id: Union[str, int]) -> list:
        """Get list of source short names disabled by user."""
        user_id = str(user_id)
        doc = await self.users.find_one({"_id": user_id}, {"setting.disabled_sources": 1})
        return doc.get("setting", {}).get("disabled_sources", []) if doc else []

    @async_slogs
    async def toggle_user_source(self, user_id: Union[str, int], sf: str) -> bool:
        """
        Toggle user source preference between enabled and disabled.
        Returns True if source is now ENABLED for user, False if now DISABLED.
        """
        user_id = str(user_id)
        disabled_sources = await self.get_user_disabled_sources(user_id)

        if sf in disabled_sources:
            await self.users.update_one(
                {"_id": user_id},
                {"$pull": {"setting.disabled_sources": sf}}
            )
            return True  # Now enabled
        else:
            await self.users.update_one(
                {"_id": user_id},
                {"$addToSet": {"setting.disabled_sources": sf}}
            )
            return False  # Now disabled

    @async_slogs
    async def is_source_enabled_for_user(self, user_id: Union[str, int], sf: str) -> bool:
        """Check if source is enabled by the specific user."""
        disabled_sources = await self.get_user_disabled_sources(user_id)
        return sf not in disabled_sources

    @async_slogs
    async def is_source_available(self, user_id: Union[str, int], sf: str) -> bool:
        """Check if source is available (globally enabled AND enabled for user)."""
        globally_enabled = await self.is_source_globally_enabled(sf)
        if not globally_enabled:
            return False
        return await self.is_source_enabled_for_user(user_id, sf)

    @async_slogs
    async def close(self):
        """Close database connections."""
        if hasattr(self, "_db") and self._db.client:
            await self._db.client.close()
            logger.info("Database connections closed")


# Global database instance
database = MangaDB()

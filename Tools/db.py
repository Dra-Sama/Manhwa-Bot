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
"""


import time
import re
from typing import Optional, Dict, List, Any, AsyncGenerator, Union
from functools import wraps

from loguru import logger
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError

from bot import Vars
from operator import itemgetter
from pyrogram.types import Message

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


def get_episode_number(text: str) -> Optional[str]:
    """Extract episode/chapter number from text."""
    if not text:
        return None

    text = str(text).strip()

    # Ordered patterns by specificity
    patterns = [
        # Chapter patterns
        (r"Chapter\s+(\d+(?:\.\d+)?)", 1),
        (r"Vol(?:ume)?\.?\s*(\d+)\s+Chapter\s+(\d+(?:\.\d+)?)", 2),
        (r"Ch(?:apter)?\.?\s*(\d+)\s*[-\u2013\u2014]\s*(\d+(?:\.\d+)?)", 2),
        (r"Ep(?:isode)?\.?\s*(\d+(?:\.\d+)?)", 1),
        (r'\bCh(?:apter)?[.\- ]?(\d+(?:\.\d+)?)\b', 1),
        (r'\bChap(?:ter)?[.\- ]?(\d+(?:\.\d+)?)\b', 1),
        (r'\bC[.\- ]?(\d+(?:\.\d+)?)\b', 1),
        (r'\[Ch(?:apter)?[.\- ]?(\d+(?:\.\d+)?)\]', 1),
        (r'\[C[.\- ]?(\d+(?:\.\d+)?)\]', 1),
        (r'Vol[.\- ]?\d+[.\- ]?Ch(?:apter)?[.\- ]?(\d+(?:\.\d+)?)', 1),
        (r'V\d+[.\- ]?C[.\- ]?(\d+(?:\.\d+)?)', 1),
        (r'\b(?:ch|chapter|chap)?[._\- ]?(\d+(?:\.\d+)?)(?!\d)', 1),
        (r'\b(\d{1,4}(?:\.\d+)?)\b', 1),
        (r'(?<!\d)(\d{1,4}(?:\.\d+)?)(?!\d)', 1),
        (r"\b(\d+(?:\.\d+)?)\b", 1),
    ]

    for pattern, group in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(group) if match.lastindex and match.lastindex >= group else match.group(1)

    return None


def get_effective_user_id(user_id: int | Message | str) -> str:
    """Returns a shared ID for admins if IS_PRIVATE is True."""
    if isinstance(user_id, Message):
        user_id = user_id.from_user.id

    try: 
        user_id = int(user_id)
    except Exception:
        user_id = "shared_admin_subs"

    if user_id == "shared_admin_subs":
        return "shared_admin_subs"

    if Vars.IS_PRIVATE and user_id in Vars.ADMINS:
        return "shared_admin_subs"
    
    return str(user_id)


slugs_sites = ["cx", "as"]
class MangaDB:
    """A class to manage manga data in the database."""
    __slots__ = ('users', 'acollection', '_db')

    def __init__(self):
        """Initialize database connections."""
        client = AsyncMongoClient(Vars.DB_URL)
        
        self._db = client[Vars.DB_NAME]
        self.users = self._db.users
        self.acollection = self._db.premium
    

    @async_slogs
    async def ensure_user(self, user_id: Union[str, int]) -> bool:
        """Ensure user exists in database, create if not."""
        user_id = str(user_id)
        
        user_data = await self.users.find_one(
            {"_id": user_id},
            {"_id": 1}  # Only fetch _id for existence check
        )

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
        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {e}")
            return False

    async def get_users(self, user_id: Optional[Union[str, int]] = None) -> AsyncGenerator[Dict, None]:
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
    
    """ Settings """
    @async_slogs
    async def get_settings(self, user_id: Union[str, int]):
        """Get user settings."""
        user_id = str(user_id)
        user_data = await self.users.find_one(
            {"_id": user_id},
            {"setting": 1}
        )
        return user_data.get("setting", {}) if user_data else {}

    @async_slogs
    async def get_value(self, user_id: Union[str, int], key: str):
        """Get specific setting value for user."""
        user_id = str(user_id)
        user_data = await self.users.find_one(
            {"_id": user_id},
            {f"setting.{key}": 1}
        )
        return user_data.get("setting", {}).get(key, None) if user_data else None
    
    @async_slogs
    async def set_value(self, user_id: Union[str, int], key: str, value: Any):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {f"setting.{key}": value}}
        )
        return None
    
    @async_slogs
    async def delete_value(self, user_id: Union[str, int], key: str):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$unset": {f"setting.{key}": ""}}
        )
        return None
    
    
    @async_slogs
    async def get_channels(self, user_id: Union[str, int], channel_type: str):
        user_id = str(user_id)
        user_data = await self.users.find_one(
            {"_id": user_id},
            {channel_type: 1}
        )
        return user_data.get(channel_type, []) if user_data else []
    
    @async_slogs
    async def erase_channel(self, user_id: Union[str, int], channel_type: str):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {channel_type: []}}
        )
        return None

    @async_slogs
    async def add_channel(self, user_id: Union[str, int], channel_type: str, channel_id: int):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$addToSet": {channel_type: channel_id}}
        )
        return None

    @async_slogs
    async def remove_channel(self, user_id: Union[str, int], channel_type: str, channel_id: int):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$pull": {channel_type: channel_id}}
        )
        return None
    
    @async_slogs
    async def get_target_channel(self, user_id: Union[str, int]):
        user_id = str(user_id)
        user_data = await self.users.find_one(
            {"_id": user_id},
            {"target_channels": 1}
        )
        return user_data.get("target_channels", []) if user_data else []
    
    @async_slogs
    async def get_auto_channel(self, user_id: Union[str, int]):
        user_id = str(user_id)
        user_data = await self.users.find_one(
            {"_id": user_id},
            {"auto_channels": 1}
        )
        return user_data.get("auto_channels", []) if user_data else []

    @async_slogs
    async def add_target_channel(self, user_id: Union[str, int], channel_id: int):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$addToSet": {"target_channels": channel_id}}
        )
        return None

    @async_slogs
    async def add_auto_channel(self, user_id: Union[str, int], channel_id: int):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$addToSet": {"auto_channels": channel_id}}
        )
        return None

    @async_slogs
    async def remove_target_channel(self, user_id: Union[str, int], channel_id: int):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$pull": {"target_channels": channel_id}}
        )
        return None

    @async_slogs
    async def remove_auto_channel(self, user_id: Union[str, int], channel_id: int):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$pull": {"auto_channels": channel_id}}
        )
        return None
    
    @async_slogs
    async def erase_target_channel(self, user_id: Union[str, int]):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {"target_channels": []}}
        )
        return None
    
    @async_slogs
    async def erase_auto_channel(self, user_id: Union[str, int]):
        user_id = str(user_id)
        await self.users.update_one(
            {"_id": user_id},
            {"$set": {"auto_channels": []}}
        )
        return None
    
    @async_slogs
    async def check_dump(self, channel_id: Union[str, int]) -> Optional[str]:
        """Check if channel is configured as dump or auto channel for any user."""
        channel_id = int(channel_id)

        user_data = await self.users.find_one({
            "$or": [
                {"setting.dump": channel_id},
                {"target_channels": channel_id},                       
                {"auto_channels": channel_id}
            ]
        })

        if user_data and user_data.get('_id'):
            return str(user_data['_id'])

        return None

    """ Subscriptions """
    @async_slogs
    async def add_sub(
        self, 
        user_id: Union[str, int], 
        rdata: Any, 
        web: str, 
        chapter: Optional[str] = None
    ) -> bool:
        """Add subscription for user."""
        user_id = get_effective_user_id(user_id)
        result = None
        
        if not await self.ensure_user(user_id):
            return False

        if hasattr(rdata, 'load_to_dict'):
            rdata = rdata.load_to_dict()

        if not isinstance(rdata, dict):
            logger.error(f"Invalid rdata type: {type(rdata)}")
            return False

        
        if chapter and 'lastest_chapter' not in rdata:
            rdata['lastest_chapter'] = chapter
        
        manga_url = str(rdata.get('url'))
        if (web and web == "as") or (manga_url and manga_url.startswith("https://asuracomic")):
            try:
                slugs = manga_url.split("/")[-1]
                slugs = "-".join(slugs.split("-")[:-1])
                rdata['slugs'] = slugs
            
                result = await self.users.update_one(
                    {
                        "_id": user_id,
                        f"subs.{web}.slugs": {"$ne": slugs}
                    },
                    {
                        "$push": {
                            f"subs.{web}": rdata
                        }
                    }
                )
            except Exception:
                pass
        
        if result and result.modified_count:
            return True 
        
        result = await self.users.update_one(
            {
                "_id": user_id,
                f"subs.{web}.url": {"$ne": manga_url}  # ensure URL not already in array
            },
            {
                "$push": {
                    f"subs.{web}": rdata
                }
            }
        )
        
        return True if result.modified_count else False

    @async_slogs
    async def check_sub(
        self, 
        user_id: Union[str, int], 
        manga_url: Optional[str] = None, 
        web: Optional[str] = None
    ) -> bool:
        """Check if user has subscription."""
        user_id = get_effective_user_id(user_id)

        if not manga_url and not web:
            user_data = await self.users.find_one(
                {"_id": user_id},
                {"subs": 1}
            )
            return bool(user_data and user_data.get("subs"))

        query = {"_id": user_id}

        if manga_url and web:
            query[f"subs.{web}.url"] = manga_url
            
        elif manga_url:
            # Check across all web entries
            query["subs"] = {"$elemMatch": {"url": manga_url}}
            
        elif web:
            query[f"subs.{web}"] = {"$exists": True, "$ne": []}

        user_data = await self.users.find_one(query, {"_id": 1})
        
        return user_data is not None

    @async_slogs
    async def delete_sub(
        self, 
        user_id: Union[str, int], 
        manga_url: Optional[str] = None, 
        web: Optional[str] = None
    ) -> bool:
        """Delete subscription(s) for user."""
        user_id = get_effective_user_id(user_id)

        if not await self.check_sub(user_id, manga_url, web):
            return False

        update_query = {}
        if (web and web == "as") or (manga_url and manga_url.startswith("https://asuracomic")):
            try:
                slugs = str(manga_url).split("/")[-1]
                slugs = "-".join(slugs.split("-")[:-1])
                
                update_query["$pull"] = {f"subs.{web}": {"slugs": slugs}}
            except Exception:
                pass
        
        elif manga_url and web:
            # Remove specific manga from specific web
            update_query["$pull"] = {f"subs.{web}": {"url": manga_url}}
        
        elif manga_url:
            # Remove manga from all webs
            # This is more complex as we need to update all web arrays
            user_data = await self.users.find_one(
                {"_id": user_id},
                {"subs": 1}
            )

            if not user_data or not user_data.get("subs"):
                return False

            updates = {}
            for web_key, subs_list in user_data["subs"].items():
                if isinstance(subs_list, list):
                    updates[f"subs.{web_key}"] = [
                        sub for sub in subs_list 
                        if sub.get('url') != manga_url
                    ]

            if updates:
                result = await self.users.update_one(
                    {"_id": user_id},
                    {"$set": updates}
                )
                return result.modified_count > 0
            
            return False
        elif web:
            # Remove entire web category
            update_query["$unset"] = {f"subs.{web}": ""}
        else:
            # Remove all subscriptions
            update_query["$set"] = {"subs": {}}

        result = await self.users.update_one(
            {"_id": user_id},
            update_query
        )

        success = result.modified_count > 0
        if success:
            logger.debug(f"Deleted subscription(s) for user {user_id}")

        return success

    @async_slogs
    async def get_subs(
        self, 
        user_id: Union[str, int], 
        manga_url: Optional[str] = None, 
        web: Optional[str] = None
    ) -> Optional[Union[List, Dict]]:
        """Get user's subscriptions."""
        
        user_id = get_effective_user_id(user_id)
        udata = await self.users.find_one({"_id": user_id})
        udata = udata.get("subs", {}) if udata else {}
        
        if not udata:
            return None
        
        rdata = []
        if not manga_url and not web:
            return [
                chapter_data
                for subs in udata.values()
                for chapter_data in subs
            ]
        
        if web:
            rdata = udata.get(web, [])
        
        if rdata and not manga_url:
            return rdata
        
        get_url = itemgetter('url')
        if rdata and manga_url:
            if (web and web == "as") or (manga_url and manga_url.startswith("https://asuracomic")):
                try:
                    slugs = manga_url.split("/")[-1]
                    slugs = "-".join(slugs.split("-")[:-1])
                    get_slugs = itemgetter("slugs")
                    return next(sub for sub in rdata if slugs in get_slugs(slugs) == slugs)
                except Exception:
                    pass
            try:
                return next(sub for sub in rdata if get_url(sub) == manga_url)
            except (StopIteration, KeyError):
                return None

        # Only Manga Url is Given
        if manga_url:
            try:
                return next(
                    sub 
                    for subs in udata.values()
                    for sub in subs 
                    if get_url(sub) == manga_url
                )
            except Exception:
                return None

        return None


    async def get_all_subs(self) -> AsyncGenerator:
        """Get all users with subscriptions."""
        
        async for user_data in self.users.find(
            { "subs": { "$exists": True } },
            { "_id": 1, "subs": 1 }
        ):
            yield user_data

    @async_slogs
    async def save_latest_chapter(
        self, 
        data: Dict, 
        user_id: Union[str, int], 
        web_sf: str
    ):
        """Update the latest chapter for subscribed manga."""
        try:
            
            user_id = get_effective_user_id(user_id)
            
            # Filter and prepare data
            main_keys = ["title", "url", "lastest_chapter", "slugs"]
            filtered_data = {k: data.get(k) for k in main_keys if k in data}

            if 'url' not in filtered_data:
                logger.error("No URL provided in data")
                return False
            
            manga_url = str(filtered_data['url'])
            if (web_sf and web_sf == "as") or (manga_url.startswith("https://asuracomic")):
                try:
                    slugs = manga_url.split("/")[-1]
                    slugs = "-".join(slugs.split("-")[:-1])
                    check = await self.users.find_one(
                        {
                            "_id": user_id,
                            f"subs.{web_sf}.slugs": slugs
                        }
                    )
                    if check:
                        await self.users.update_one(
                            { "_id": user_id, f"subs.{web_sf}.slugs": slugs },
                            { "$set": { f"subs.{web_sf}.$": filtered_data } }
                        )
                        return True
                except Exception:
                    pass
            
            # Update the subscription
            result = await self.users.update_one(
                {
                    "_id": user_id,
                    f"subs.{web_sf}.url": filtered_data['url']
                },
                {
                    "$set": {f"subs.{web_sf}.$": filtered_data}
                }
            )

            success = result.modified_count > 0
            if success:
                logger.debug(f"Updated latest chapter for user {user_id}, web {web_sf}")
            
            return success

        except Exception as err:
            logger.exception(f"Error saving latest chapter: {err}")
            return False

    """ Export/Import """
    @async_slogs
    async def get_full_user_data(self, user_id: Union[str, int]) -> Dict:
        """Get full user data for export."""
        user_id = get_effective_user_id(user_id)
        user_data = await self.users.find_one(
            {"_id": user_id},
            {"subs": 1, "target_channels": 1, "auto_channels": 1}
        )
        if not user_data:
            return {}
        
        return {
            "subs": user_data.get("subs", {}),
            "target_channels": user_data.get("target_channels", []),
            "auto_channels": user_data.get("auto_channels", [])
        }

    @async_slogs
    async def update_user_data(self, user_id: Union[str, int], data: Dict) -> bool:
        """Update user data from imported JSON."""
        user_id = get_effective_user_id(user_id)
        if not await self.ensure_user(user_id):
            return False

        update_query = {}
        # Handle 'subs' or 'subscriptions'
        subs_data = data.get("subs") or data.get("subscriptions")
        if subs_data:
            if isinstance(subs_data, list):
                # Convert list of subs to dict grouped by 'web'
                formatted_subs = {}
                for sub in subs_data:
                    web = sub.get("web") or "default"
                    if web not in formatted_subs:
                        formatted_subs[web] = []
                    
                    # Map 'url' and 'title' keys correctly
                    mapped_sub = {
                        "url": sub.get("url") or sub.get("manga_url"),
                        "title": sub.get("title") or sub.get("manga_title"),
                        "lastest_chapter": sub.get("lastest_chapter")
                    }
                    # Filter out None values
                    mapped_sub = {k: v for k, v in mapped_sub.items() if v is not None}
                    
                    formatted_subs[web].append(mapped_sub)
                update_query["subs"] = formatted_subs
            else:
                update_query["subs"] = subs_data

        for key in ["target_channels", "auto_channels"]:
            if key in data:
                update_query[key] = data[key]

        if not update_query:
            logger.warning(f"No valid keys found in import data for user {user_id}")
            return False

        result = await self.users.update_one(
            {"_id": user_id},
            {"$set": update_query}
        )
        # Return True if successfully acknowledged, even if no changes were made (already identical)
        return result.acknowledged

    """ Premium """
    def parse_duration(self, duration_str: str) -> int:
        """Parse duration string like '1 day', '1 month' into days."""
        try:
            # Handle cases like "1day", "1 day", "1 days", "1  day"
            match = re.search(r'(\d+)\s*([a-zA-Z]+)', str(duration_str).strip())
            if not match:
                # If only a number is provided, assume it's days
                return int(duration_str)
            
            value = int(match.group(1))
            unit = match.group(2).lower()
            
            if unit.startswith('day'):
                return value
            elif unit.startswith('week'):
                return value * 7
            elif unit.startswith('month'):
                return value * 30
            elif unit.startswith('year'):
                return value * 365
            else:
                return value # Default to days if unit is unknown
        except Exception:
            try:
                return int(duration_str)
            except Exception:
                return 0

    @async_slogs
    async def add_premium(self, user_id: Union[str, int], time_limit: Union[int, str]) -> bool:
        """Add premium status to user."""
        user_id = str(user_id)
        
        if isinstance(time_limit, str):
            time_limit_days = self.parse_duration(time_limit)
        else:
            time_limit_days = time_limit

        expiration_timestamp = int(time.time()) + (time_limit_days * 24 * 60 * 60)

        result = await self.acollection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "expiration_timestamp": expiration_timestamp,
                    "added_at": int(time.time())
                }
            },
            upsert=True
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

        result = await self.acollection.delete_many({
            "expiration_timestamp": {"$lt": current_timestamp}
        })

        count = result.deleted_count
        if count > 0:
            logger.info(f"Removed {count} expired premium users")

        return count

    async def get_all_premium(self) -> AsyncGenerator:
        """Get all premium user IDs."""
        async for doc in self.acollection.find(
            {"expiration_timestamp": {"$gt": int(time.time())}}
        ):
            if doc and doc.get('_id'):
                yield str(doc['_id']), doc

    @async_slogs
    async def premium_user(self, user_id: Union[str, int]) -> Optional[Dict]:
        """Check if user has active premium status."""
        user_id = str(user_id)
        current_timestamp = int(time.time())

        user_data = await self.acollection.find_one({
            "_id": user_id,
            "expiration_timestamp": {"$gt": current_timestamp}
        })

        return user_data

    async def is_authorized(self, user_id: Union[str, int]) -> bool:
        """Check if user is authorized (admin or premium)."""
        if not Vars.IS_PRIVATE:
            return True
            
        # Admin check
        if user_id in Vars.ADMINS:
            return True
        try:
            if int(user_id) in Vars.ADMINS:
                return True
        except (ValueError, TypeError):
            pass
            
        # Premium check
        if await self.premium_user(user_id):
            return True
            
        return False

    @async_slogs
    async def close(self):
        """Close database connections."""
        if hasattr(self, '_db') and self._db.client:
            await self._db.client.close()
            logger.info("Database connections closed")


# Global database instance
database = MangaDB()

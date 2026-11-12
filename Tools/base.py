# Code By @V_Sbotmaker (on Telegram)
from __future__ import annotations

import collections
import asyncio
import random
import shutil
import string
import time
from collections import OrderedDict
from collections.abc import MutableMapping
from functools import wraps
from os import path as ospath
from threading import RLock, Timer
from typing import Any, Dict, Iterator, Optional, Tuple

import pyrogram.errors
from natsort import natsorted, ns
from pyrogram.errors import FloodWait

import psutil

from bot import Bot, Vars, logger
from .db import database, get_episode_number
from .img2pdf import thumbnali_images
from .ihandler import ihandler
from itertools import chain


# ──────────────────────────────────────────────────────────────────────────────
_REMOVE_CHARS = "_&;:'|*?><`!@#$%^~+=/\\\n"
_TRANSLATOR   = str.maketrans("", "", _REMOVE_CHARS)


def clean(txt: str, length: int = -1) -> str:
    txt = txt.translate(_TRANSLATOR)
    txt = txt.replace("None", "").replace(".jpg", "")
    return txt[:length] if length != -1 else txt


# ──────────────────────────────────────────────────────────────────────────────
# Decorators
# ──────────────────────────────────────────────────────────────────────────────

def igrone_error(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception:
            return None
    return wrapper


def log(func, r: bool = False):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.exception(f"Error in {func.__name__}: {e}")
            if r:
                raise
            return None
    return wrapper


def retry_on_flood(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        while True:
            try:
                return await func(*args, **kwargs)

            except FloodWait as e:
                wait = int(e.value) + 3
                logger.warning(f"FloodWait: waiting {wait}s")
                await asyncio.sleep(wait)

            except pyrogram.errors.exceptions.bad_request_400.InputUserDeactivated:
                chat_id = kwargs.get("chat_id")
                if chat_id:
                    await database.delete_user(chat_id)
                break

            except (
                ValueError,
                pyrogram.errors.QueryIdInvalid,
                pyrogram.errors.MessageNotModified,
                pyrogram.errors.exceptions.bad_request_400.ChannelInvalid,
            ):
                raise

            except ConnectionError:
                raise

            except (
                pyrogram.errors.exceptions.bad_request_400.WebpageCurlFailed,
                pyrogram.errors.exceptions.bad_request_400.WebpageMediaEmpty,
                pyrogram.errors.exceptions.bad_request_400.PeerIdInvalid,
                pyrogram.errors.exceptions.bad_request_400.UsernameNotOccupied,
                pyrogram.errors.exceptions.bad_request_400.BadRequest,
                pyrogram.errors.exceptions.bad_request_400.MessageIdInvalid,
            ):
                raise

            except Exception as e:
                if "stat: path should be string" in str(e):
                    raise
                logger.exception(e)
                raise

    return wrapper


# ──────────────────────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────────────────────

class MangaCard:
    __slots__ = ("url", "title", "poster", "msg", "chapters", "webs", "data")

    def __init__(
        self,
        webs=None,
        url: str = "",
        title: str = "",
        poster: str = "",
        msg: str = "",
        chapters=None,
        data=None,
    ):
        self.url      = url
        self.title    = title
        self.poster   = poster
        self.msg      = msg
        self.chapters = [] if chapters is None else chapters
        self.webs     = webs
        self.data     = {} if data is None else data

    def __repr__(self) -> str:
        return f"MangaCard({self.title})"

    def load_to_class(self, data: dict) -> "MangaCard":
        for key, val in data.items():
            if key in self.__slots__:
                setattr(self, key, val)
            else:
                self.data[key] = val
        return self

    def load_to_dict(self) -> dict:
        result = {}
        for key in self.__slots__:
            if key == "data":
                result.update(self.data)
            else:
                result[key] = getattr(self, key)
        return result

    def update_dict(self, data: dict) -> None:
        for key, val in data.items():
            if key in self.__slots__:
                setattr(self, key, val)
            else:
                self.data[key] = val

    @classmethod
    def from_dict(cls, data: dict) -> "MangaCard":
        obj = cls.__new__(cls)
        obj.url      = ""
        obj.title    = ""
        obj.poster   = ""
        obj.msg      = ""
        obj.chapters = []
        obj.webs     = None
        obj.data     = {}
        obj.load_to_class(data)
        return obj


class Subscribes:
    """Manages user-specific subscriptions."""

    __slots__ = ("user_id", "manga_url", "webs", "lastest_chapter", "manga_title")

    def __init__(
        self,
        webs: str,
        manga_url: str,
        lastest_chapter: str,
        manga_title: str,
        user_id: str = "",
    ):
        self.user_id        = user_id
        self.manga_url      = manga_url
        self.manga_title    = manga_title
        self.webs           = webs
        self.lastest_chapter = lastest_chapter

    def load_to_dict(self) -> dict:
        return {
            "url": self.manga_url,
            "title": self.manga_title,
            "lastest_chapter": self.lastest_chapter,
        }


# ──────────────────────────────────────────────────────────────────────────────
# File-name helpers
# ──────────────────────────────────────────────────────────────────────────────

def get_file_name(data: list, setting: dict = {}) -> Tuple[str, str, str]:
    regex = setting.get("regex")
    try:
        flen = int(setting.get("file_name_len", 30))
    except (TypeError, ValueError):
        flen = 30

    def _ep(item: dict) -> str:
        raw = str(get_episode_number(item.get("title", "None")))
        if not raw or raw == "None":
            return clean(item.get("title", "None"))
        return raw.zfill(int(regex)) if regex else raw

    if len(data) > 1:
        episode_number = f"{_ep(data[0])} - {_ep(data[-1])}"
    else:
        episode_number = _ep(data[0])

    original_manga_title = data[0].get("manga_title", "")
    manga_title = clean(original_manga_title, flen)
    return original_manga_title, manga_title, episode_number


# ──────────────────────────────────────────────────────────────────────────────
# Thumbnail helpers
# ──────────────────────────────────────────────────────────────────────────────

async def process_thumbnail_pdf(thumb_path: Optional[str]) -> Optional[str]:
    import os
    from PIL import Image, ImageOps

    if not thumb_path or not os.path.exists(thumb_path):
        return None
    try:
        def _process():
            img = Image.open(thumb_path).convert("RGB")
            img = ImageOps.contain(img, (320, 320), Image.LANCZOS)
            img = ImageOps.pad(img, (320, 320), color=(0, 0, 0))
            img.save(thumb_path, "JPEG", quality=95)

        await asyncio.to_thread(_process)
    except Exception:
        pass
    return thumb_path


def _s64_sync(b6: str, fp: str) -> Optional[str]:
    import base64
    try:
        if b6.startswith("data:"):
            b6 = b6.split(",", 1)[1]

        with open(fp, "wb") as f:
            f.write(base64.b64decode(b6))

        return fp
    except Exception:
        return None


async def load_images_(
    u_id,
    p,
    b_url=None,
    p_fn=None,
    us: Optional[dict] = None,
) -> dict:
    """
    Resolve banner/thumbnail images for a user.

    Args:
        u_id : User Id
        p    : poster url
        b_url: base url
        p_fn : poster file name
        us   : pre-fetched user settings (fetched here if None)
    """
    import os

    md = f"Process/{u_id}"
    await asyncio.to_thread(os.makedirs, md, exist_ok=True)

    if not us:
        us = await database.get_settings(u_id)

    prs = [
        ("banner1_file_path", us.get("banner1")),
        ("banner2_file_path", us.get("banner2")),
        ("thumb_file_name",   us.get("thumb")),
    ]

    async def _s64(b6: str, fp: str) -> Optional[str]:
        # base64-decode + file write is blocking disk I/O - keep it off the
        # event loop so a burst of concurrent tasks doesn't stall on it.
        return await asyncio.to_thread(_s64_sync, b6, fp)

    async def _resolve(k: str, v: Optional[str]) -> Tuple[str, Optional[str]]:
        fp = f"{md}/{k}.jpg"
        if ospath.exists(fp):
            return k, fp
        if not v:
            return k, None

        if v.startswith("http"):
            t = await igrone_error(thumbnali_images)(
                image_url=v, download_dir=md, file_name=k
            )
            return k, await process_thumbnail_pdf(t)

        if v.startswith("data:image"):
            return k, await _s64(v, fp)

        if v.startswith("/9j") or v.startswith("iVBOR") or len(v) > 500:
            t = await _s64(v, fp)
            if t:
                return k, t
            t = await igrone_error(Bot.download_media)(v, file_name=fp)
            return k, await process_thumbnail_pdf(t)

        if p and v == "constant":
            t = await igrone_error(thumbnali_images)(
                image_url=p, download_dir="Process/Poster",
                file_name=p_fn, base_url=b_url
            )
            return k, await process_thumbnail_pdf(t)

        t = await igrone_error(Bot.download_media)(v, file_name=fp)
        return k, await process_thumbnail_pdf(t)

    results = await asyncio.gather(*[_resolve(k, v) for k, v in prs])
    return dict(results)


# ──────────────────────────────────────────────────────────────────────────────
# TaskCard
# ──────────────────────────────────────────────────────────────────────────────

class TaskCard:
    """Manages a single download + conversion task."""
    __slots__ = (
        "data_list", "chapters_urls", "url", "poster",
        "webs", "sts", "setting",
        "orginal_manga_title", "manga_title", "episode_number",
        "tasks_id", "user_id", "chat_id", "priority",
        "update_mode", "status",
        "main_dir", "compressed_dir",   
    )

    def __init__(
        self,
        webs,
        sts,
        user_id,
        chat_id,
        priority,
        tasks_id=None,
        data_list: Optional[list] = None,
        update_mode: bool = False,
        settings: Optional[dict] = None,
    ):
        self.data_list      = data_list or []
        self.chapters_urls  = [d.get("url") for d in self.data_list]

        if len(self.chapters_urls) == 1:
            self.url = self.chapters_urls[0]
        else:
            self.url = self.chapters_urls[0] + "-" + self.chapters_urls[-1]

        self.poster   = data_list[0].get("poster") if data_list else ""
        self.webs     = webs
        self.sts      = sts
        self.setting  = settings or {}

        self.orginal_manga_title, self.manga_title, self.episode_number = get_file_name(
            self.data_list, self.setting
        )

        self.tasks_id    = tasks_id
        self.user_id     = user_id
        self.chat_id     = chat_id
        self.priority    = priority
        self.update_mode = update_mode
        self.status      = "In Queue"

        self.main_dir       = None
        self.compressed_dir = None

    async def close(self) -> None:
        async def _rm() -> None:
            if self.main_dir and ospath.exists(self.main_dir):
                try:
                    # rmtree is blocking disk I/O - run it off the event
                    # loop. It also runs concurrently with release_batch()
                    # below (they're independent), which shaves latency off
                    # close() - and close() is what frees this user's
                    # ongoing-task slot for their next queued item.
                    await asyncio.to_thread(shutil.rmtree, self.main_dir, ignore_errors=True)
                except Exception as e:
                    logger.warning(f"TaskCard.close() error for {self.tasks_id}: {e}")

        await asyncio.gather(_rm(), ihandler.release_batch(self.chapters_urls))

    def schedule_order(self) -> None:
        self.main_dir       = f"Process/{self.tasks_id}"
        self.compressed_dir = f"{self.main_dir}/compress"
        ihandler.order_batch(str(self.user_id), self.webs, [(d.get("url"), d) for d in self.data_list])

    async def get_images_paths(self) -> Optional[list]:
        for attempt in range(1, 4):
            try:
                chapters     = await ihandler.get_batch(self.chapters_urls)
                images_paths = list(chain.from_iterable(chapters))
            except Exception as e:
                # get_batch() raises once a chapter fails all of its own
                # internal retries. Without catching this here, the
                # exception blew straight past this whole retry loop on
                # the very first attempt, so schedule_order()'s re-queue
                # never actually got a chance to run - and if the caller
                # of get_images_paths() didn't also catch it, the task
                # never reached close(), permanently leaking the reader
                # counts get_batch() had already acquired for any chapters
                # that DID succeed.
                logger.warning(
                    f"get_batch failed for task {self.tasks_id} "
                    f"(attempt {attempt}): {e}"
                )
                images_paths = []

            if images_paths:
                return images_paths

            self.status = f"Downloading {len(self.chapters_urls)} chapters (retry {attempt})"
            ihandler.order_batch(str(self.user_id), self.webs, [(d.get("url"), d) for d in self.data_list])
            await asyncio.sleep(10)

        return None

    async def get_banner(self) -> dict:
        try:
            us = await database.get_settings(self.user_id)
            if not isinstance(us, dict):
                return {}

            kwargs: dict = {
                "u_id":  self.user_id,
                "p":     None,
                "b_url": self.webs.url,
                "p_fn":  self.manga_title,
                "us":    us,
            }

            poster_url = None
            is_constant = str(us.get("thumb")) == "constant"

            if is_constant and self.poster:
                entry = await ihandler.get_storage(self.poster)
                if entry is not None:
                    poster_url = entry
                    await ihandler.release_storage(self.poster)

            if not poster_url:
                kwargs["p"] = self.poster

            rdata = await asyncio.wait_for(load_images_(**kwargs), 10 * 60)

            if is_constant and rdata.get("thumb_file_name"):
                await ihandler.set_storage(self.poster, rdata["thumb_file_name"])

            if poster_url:
                rdata["thumb_file_name"] = poster_url

            return rdata
        except asyncio.TimeoutError:
            return {}

        except Exception as er:
            logger.exception(f"Error in get_banner: {er}")
            return {}


# ──────────────────────────────────────────────────────────────────────────────
# AQueue
# ──────────────────────────────────────────────────────────────────────────────

class AQueue:
    __slots__ = (
        "storage_data", "ongoing_tasks",
        "maxsize", "_sorted_dirty", "_event",
        "_lock", "_rr_queues", "_rr_users", "_rr_idx"
    )

    def __init__(self, maxsize: Optional[int] = None):
        
        # task_id -> (TaskCard, is_update)
        self.storage_data:  Dict[str, Tuple[TaskCard, bool]] = {}

        # user_id -> List[TaskCard]  (multiple ongoing per user, one per worker)
        self.ongoing_tasks: Dict[str, list]                  = {}
        self.maxsize       = maxsize
        self._sorted_dirty = False
        self._event        = asyncio.Event()
        self._lock         = asyncio.Lock()

        # RR Scheduler structures
        self._rr_queues: Dict[str, Dict[int, collections.deque]] = {}
        self._rr_users: List[str] = []
        self._rr_idx: int = 0

    # ── internal helpers ──────────────────────────────────────────────────────

    def _get_effective_priority(self, task: TaskCard) -> int:
        if task.update_mode:
            return 3
        if len(task.data_list) == 1:
            return 1
        return 2

    async def _random_id(self) -> str:
        chars = string.ascii_letters + string.digits
        while True:
            tid = "".join(random.choices(chars, k=7))
            # check both pending and ongoing task IDs
            ongoing_ids = {
                t.tasks_id
                for tasks in self.ongoing_tasks.values()
                for t in tasks
            }
            if tid not in self.storage_data and tid not in ongoing_ids:
                return tid

    def _resort(self) -> None:
        if not self._sorted_dirty:
            return

        self.storage_data = dict(
            natsorted(
                self.storage_data.items(),
                key=lambda x: x[1][0].episode_number,
                alg=ns.REAL,
            )
        )

        # Rebuild _rr_queues to guarantee sync and correct order
        self._rr_queues.clear()

        active_uids = []
        for task_id, (task, _) in self.storage_data.items():
            uid = str(task.user_id)
            if uid not in self._rr_queues:
                self._rr_queues[uid] = {1: collections.deque(), 2: collections.deque(), 3: collections.deque()}
                active_uids.append(uid)

            pri = self._get_effective_priority(task)
            self._rr_queues[uid][pri].append(task_id)

        new_rr_users = []
        for uid in self._rr_users:
            if uid in self._rr_queues:
                new_rr_users.append(uid)

        existing = set(new_rr_users)
        for uid in active_uids:
            if uid not in existing:
                new_rr_users.append(uid)

        self._rr_users = new_rr_users
        if self._rr_users:
            self._rr_idx = self._rr_idx % len(self._rr_users)
        else:
            self._rr_idx = 0

        self._sorted_dirty = False

    # ── public API ────────────────────────────────────────────────────────────

    async def put(self, tasks: TaskCard, updates: bool = False) -> str:
        if self.maxsize and len(self.storage_data) >= self.maxsize:
            raise asyncio.QueueFull("Queue full")

        async with self._lock:
            await database.ensure_user(tasks.user_id)
            tasks.tasks_id = await self._random_id()

            if not tasks.setting:
                tasks.setting = await database.get_settings(tasks.user_id)

            self.storage_data[tasks.tasks_id] = (tasks, updates)
            self._sorted_dirty = True
            tasks.schedule_order()
            self._event.set()

        # Notify per-user worker pool (lazy import to avoid circular dependency)
        try:
            from Tools.cworker import notify_user_task  # noqa: PLC0415
            asyncio.get_running_loop().create_task(
                notify_user_task(str(tasks.user_id))
            )
        except RuntimeError:
            pass  # no running loop yet (startup tests)
        except Exception:
            pass  # cworker not yet initialised

        # Persist to Redis (no-op if Redis unavailable)
        try:
            from Tools.redis_queue import rq  # noqa: PLC0415
            asyncio.get_running_loop().create_task(
                rq.push(tasks.tasks_id, {
                    "task_id":      tasks.tasks_id,
                    "user_id":      str(tasks.user_id),
                    "chat_id":      str(tasks.chat_id),
                    "webs_sf":      tasks.webs.sf if tasks.webs else "",
                    "chapter_urls": tasks.chapters_urls,
                    "data_list":    tasks.data_list,
                    "update_mode":  tasks.update_mode,
                    "settings":     tasks.setting or {},
                })
            )
        except RuntimeError:
            pass
        except Exception:
            pass

        return tasks.tasks_id

    def get_next_shared_task(self) -> Optional[Tuple[TaskCard, bool]]:
        """
        Fetch task for shared workers using Fair Round-Robin Scheduling.
        Ensures workers are divided equally among active users.
        """
        if psutil.virtual_memory().percent > 90.0:
            return None

        if self._sorted_dirty:
            self._resort()

        if not self._rr_users:
            return None

        # Calculate active users (users with pending or ongoing tasks)
        active_uids = set(self._rr_users)
        for uid, tasks in self.ongoing_tasks.items():
            if tasks:
                active_uids.add(uid)

        active_users_count = len(active_uids)
        if active_users_count == 0:
            return None

        shared_workers = 15
        max_concurrent = max(1, shared_workers // active_users_count + (1 if shared_workers % active_users_count else 0))
        n_users = len(self._rr_users)

        # Two-pass approach:
        # Pass 1 (strict_mode=True): Enforce fairness limit (max_concurrent) for batch tasks.
        # Pass 2 (strict_mode=False): Ignore limit to ensure 100% worker utilization if some users don't have enough tasks.
        for strict_mode in (True, False):
            for pri in [1, 2, 3]:
                # Single chapters (pri=1) bypass the limit entirely to ensure responsiveness
                if not strict_mode and pri == 1:
                    continue

                users_checked = 0
                while users_checked < n_users:
                    uid = self._rr_users[self._rr_idx]

                    if strict_mode and pri > 1:
                        current_ongoing = len(self.ongoing_tasks.get(uid, []))
                        if current_ongoing >= max_concurrent:
                            self._rr_idx = (self._rr_idx + 1) % n_users
                            users_checked += 1
                            continue

                    queue_pri = self._rr_queues[uid][pri]
                    task_id = None
                    while queue_pri:
                        tid = queue_pri[0]
                        if tid in self.storage_data:
                            task_id = tid
                            break
                        else:
                            queue_pri.popleft() # Discard invalid

                    if task_id:
                        # Found a valid task!
                        queue_pri.popleft()
                        task, is_update = self.storage_data.pop(task_id)
                        self.ongoing_tasks.setdefault(uid, []).append(task)

                        self._rr_idx = (self._rr_idx + 1) % n_users
                        return task, is_update

                    self._rr_idx = (self._rr_idx + 1) % n_users
                    users_checked += 1

        return None

    async def task_done(self, task: TaskCard):
        # We need this for cworker compatibility.
        # Let's remove from ongoing
        uid = str(task.user_id)
        if uid in self.ongoing_tasks:
            try:
                self.ongoing_tasks[uid].remove(task)
            except ValueError:
                pass
            if not self.ongoing_tasks[uid]:
                del self.ongoing_tasks[uid]
        await self.delete_task(task.tasks_id)

    def get_user_task(
        self, user_id: str, max_concurrent: int = 2
    ) -> Optional[Tuple[TaskCard, bool]]:
        """
        Return next pending task for *user_id* if the user has fewer than
        *max_concurrent* tasks currently running, otherwise None.

        This is called by each per-user worker instead of the old
        get_available_tasks() that was used by global workers.
        """
        if psutil.virtual_memory().percent > 90.0:
            return None

        self._resort()
        user_ongoing = self.ongoing_tasks.get(user_id, [])
        if len(user_ongoing) >= max_concurrent:
            return None

        for task_id, (task, is_update) in list(self.storage_data.items()):
            if str(task.user_id) != str(user_id):
                continue

            # Claim the slot
            self.ongoing_tasks.setdefault(user_id, []).append(task)
            del self.storage_data[task_id]
            return task, is_update

        return None

    # kept for backward-compat (used by auto-update worker)
    def get_available_tasks(
        self, user_id=None
    ) -> Optional[Tuple[TaskCard, bool]]:
        # This was previously returning only 1 task max for the auto update worker.
        # Now changing it to 1 max concurrent task for the auto update worker as requested.
        if psutil.virtual_memory().percent > 90.0:
            return None

        self._resort()
        for task_id, (task, is_update) in list(self.storage_data.items()):
            if user_id is not None and task.user_id != user_id:
                continue

            uid = str(task.user_id)
            user_ongoing = self.ongoing_tasks.get(uid, [])
            # allow only 1 slot via legacy path (update worker) as requested
            if len(user_ongoing) >= 1:
                continue

            self.ongoing_tasks.setdefault(uid, []).append(task)
            del self.storage_data[task_id]
            return task, is_update

        return None

    async def delete_task(self, task_id: str) -> bool:
        if task_id in self.storage_data:
            task_card, _ = self.storage_data.pop(task_id)

            # Remove from RR queue safely if we can
            uid = str(task_card.user_id)
            if uid in self._rr_queues:
                pri = self._get_effective_priority(task_card)
                if task_id in self._rr_queues[uid][pri]:
                    pass

            await igrone_error(task_card.close)()
            return True

        # Check ongoing and remove if it is just a close
        for uid, tasks_list in list(self.ongoing_tasks.items()):
            for i, t in enumerate(tasks_list):
                if str(t.tasks_id) == str(task_id):
                    # We shouldn't remove it here if it's meant to prevent cancellation,
                    # but if it's actually finished, task_done handles the removal.
                    return True
        return False

    async def delete_tasks(self, user_id: int) -> int:
        uid_str = str(user_id)
        targets = [
            (tid, pair)
            for tid, pair in list(self.storage_data.items())
            if str(pair[0].user_id) == uid_str
        ]

        async def _del(tid: str, pair: Tuple[TaskCard, bool]) -> None:
            try:
                self.storage_data.pop(tid, None)
                # Note: popleft in scheduler logic will clean up RR queue automatically
                # since the task is no longer in storage_data.
                await igrone_error(pair[0].close)()
            except Exception as e:
                logger.exception(f"Error deleting task {tid}: {e}")

        await asyncio.gather(
            *(asyncio.wait_for(_del(tid, pair), 20) for tid, pair in targets),
            return_exceptions=True,
        )
        return len(targets)

    def get_count(self, user_id: int = 0) -> int:
        try:
            if user_id == 0:
                unique: set = set()
                for task, _ in self.storage_data.values():
                    unique.add(int(task.user_id))
                for tasks_list in self.ongoing_tasks.values():
                    for task in tasks_list:
                        unique.add(int(task.user_id))
                return len(unique)
            else:
                uid_str = str(user_id)
                pending = sum(
                    1 for task, _ in self.storage_data.values()
                    if str(task.user_id) == uid_str
                )
                ongoing = len(self.ongoing_tasks.get(uid_str, []))
                return pending + ongoing
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Error counting tasks for user {user_id}: {e}")
            return 0

    def task_exists(self, task_id: str) -> bool:
        if task_id in self.storage_data:
            return True
        for tasks_list in self.ongoing_tasks.values():
            for t in tasks_list:
                if str(t.tasks_id) == str(task_id):
                    return True
        return False

    def qsize(self) -> int:
        return len(self.storage_data)

    def empty(self) -> bool:
        return not self.storage_data

    async def task_done(self, tasks_card: TaskCard) -> bool:
        uid = str(tasks_card.user_id)
        user_ongoing = self.ongoing_tasks.get(uid, [])
        if tasks_card in user_ongoing:
            user_ongoing.remove(tasks_card)
            if not user_ongoing:
                self.ongoing_tasks.pop(uid, None)
            await igrone_error(tasks_card.close)()
            self.storage_data.pop(str(tasks_card.tasks_id), None)
            self._event.set()
            # Acknowledge in Redis (no-op if Redis unavailable)
            try:
                from Tools.redis_queue import rq  # noqa: PLC0415
                asyncio.get_running_loop().create_task(
                    rq.ack(str(tasks_card.tasks_id))
                )
            except Exception:
                pass
            return True
        return False

    def get_ongoing_count(self, user_id: int) -> int:
        uid_str = str(user_id)
        return len(self.ongoing_tasks.get(uid_str, []))

    def check_queue(self, user_id: int) -> bool:
        uid = int(user_id)
        return any(int(pair[0].user_id) == uid for pair in self.storage_data.values())

    def check_poster(self, poster_url: str) -> bool:
        """
        True: Mean Donot Delete 
        False: Mean Delete
        """
        try:
            return any(pair[0].poster == poster_url for pair in self.storage_data.values())
        except Exception as e:
            logger.exception(e)

        return False


queue = AQueue()


# ──────────────────────────────────────────────────────────────────────────────
# TTLCache
# ──────────────────────────────────────────────────────────────────────────────

class TTLCache(MutableMapping):
    """
    Lightweight TTL cache backed by OrderedDict.

    All mutations (set/delete/expire) are done inside a single RLock
    acquisition so every operation is atomic from the caller's perspective.

    Args
    ----
    default_timeout  : float  seconds until an entry expires (default 2 h)
    cleanup_interval : float  background sweep interval in seconds; 0 = disabled
    maxsize          : int    cap on live entries; None = unlimited
    """

    def __init__(
        self,
        default_timeout: float = 7200.0,
        cleanup_interval: float = 0.0,
        maxsize: Optional[int] = None,
    ) -> None:
        self._data: OrderedDict[Any, Tuple[Any, float]] = OrderedDict()
        self._default_timeout = default_timeout
        self._maxsize         = maxsize
        self._lock            = RLock()
        self._cleanup_interval = cleanup_interval
        self._timer: Optional[Timer] = None
        if cleanup_interval > 0:
            self._start_cleanup_timer()

    # ── timer ─────────────────────────────────────────────────────────────────

    def _start_cleanup_timer(self) -> None:
        self._timer = Timer(self._cleanup_interval, self._periodic_cleanup)
        self._timer.daemon = True
        self._timer.start()

    def _periodic_cleanup(self) -> None:
        self._remove_expired()
        if self._cleanup_interval > 0:
            self._start_cleanup_timer()

    # ── expiry helpers ────────────────────────────────────────────────────────

    def _remove_expired(self) -> None:
        """Remove all expired entries under a single lock acquisition."""
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (_, exp) in self._data.items() if exp <= now]
            for k in expired:
                self._data.pop(k, None)

    def _evict_if_full(self) -> None:
        """Evict oldest entries while over capacity. Caller holds _lock."""
        if self._maxsize is None:
            return
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def _get_expiry(self, timeout: Optional[float] = None) -> float:
        t = timeout if timeout is not None else self._default_timeout
        return time.monotonic() + max(0.0, t)

    # ── core MutableMapping interface ─────────────────────────────────────────

    def __getitem__(self, key: Any) -> Any:
        with self._lock:
            if key not in self._data:
                raise KeyError(key)
            value, expiry = self._data[key]
            if time.monotonic() > expiry:
                del self._data[key]
                raise KeyError(key)
            self._data.move_to_end(key)
            return value

    def __setitem__(self, key: Any, value: Any) -> None:
        self.set(key, value)

    def set(self, key: Any, value: Any, timeout: Optional[float] = None) -> None:
        expiry = self._get_expiry(timeout)
        with self._lock:
            self._data[key] = (value, expiry)
            self._data.move_to_end(key)
            self._evict_if_full()

    def __delitem__(self, key: Any) -> None:
        with self._lock:
            del self._data[key]

    def __contains__(self, key: Any) -> bool:
        with self._lock:
            if key not in self._data:
                return False
            _, expiry = self._data[key]
            if time.monotonic() > expiry:
                del self._data[key]
                return False
            return True

    def get(self, key: Any, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            item = self._data.pop(key, None)
            if item is None:
                return default
            value, expiry = item
            if time.monotonic() > expiry:
                return default
            return value

    # ── iteration helpers ─────────────────────────────────────────────────────

    def _live_snapshot(self) -> list[Tuple[Any, Any]]:
        now = time.monotonic()
        with self._lock:
            return [(k, v) for k, (v, exp) in self._data.items() if exp > now]

    def keys(self):
        return [k for k, _ in self._live_snapshot()]

    def values(self):
        return [v for _, v in self._live_snapshot()]

    def items(self):
        return self._live_snapshot()

    def __len__(self) -> int:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (_, exp) in self._data.items() if exp <= now]
            for k in expired:
                self._data.pop(k, None)
            return len(self._data)

    def __iter__(self) -> Iterator[Any]:
        return iter(self.keys())

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def update(self, other: dict) -> None:
        if not other:
            return
        now     = time.monotonic()
        timeout = self._default_timeout
        with self._lock:
            for k, v in other.items():
                self._data[k] = (v, now + max(0.0, timeout))
                self._data.move_to_end(k)
            self._evict_if_full()

    def setdefault(self, key: Any, default: Any = None) -> Any:
        with self._lock:
            if key in self._data:
                value, expiry = self._data[key]
                if time.monotonic() <= expiry:
                    self._data.move_to_end(key)
                    return value
            expiry = self._get_expiry()
            self._data[key] = (default, expiry)
            self._data.move_to_end(key)
            self._evict_if_full()
            return default

    # ── convenience extras ────────────────────────────────────────────────────

    def get_expiry_time(self, key: Any) -> Optional[float]:
        with self._lock:
            item = self._data.get(key)
            if item is not None:
                _, exp = item
                if time.monotonic() <= exp:
                    return exp
        return None

    def refresh_key(self, key: Any, timeout: Optional[float] = None) -> bool:
        with self._lock:
            item = self._data.get(key)
            if item is not None:
                value, exp = item
                if time.monotonic() <= exp:
                    self._data[key] = (value, self._get_expiry(timeout))
                    self._data.move_to_end(key)
                    return True
        return False

    # ── context manager + lifecycle ───────────────────────────────────────────

    def __repr__(self) -> str:
        return f"TTLCache({dict(self.items())})"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.clear()
        if self._timer and self._timer.is_alive():
            self._timer.cancel()

    def __del__(self):
        if self._timer and self._timer.is_alive():
            self._timer.cancel()

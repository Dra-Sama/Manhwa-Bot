# Code By @V_Sbotmaker (on Telegram)
"""
We have 100+ users and 100K chapters download per min.
We need something fastest and lightweight..
"""

from __future__ import annotations
import contextlib

import os
import shutil
import time
import uuid
import asyncio
from typing import Optional, Any

from loguru import logger

from .img2pdf import download_and_convert_images, download_images_sb


# --------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------- #
TIME_EXPIRE  = 2 * 60 * 60   # 2 hours
_GET_TIMEOUT = 20 * 60        # wait up to 20 min for an in-progress order
USER_LIMIT   = 10
_USER_SEM_IDLE_TTL = 30 * 60  # drop an unused per-user semaphore after 30 min idle

# --------------------------------------------------------------------- #
# Internal data classes
# --------------------------------------------------------------------- #

class _CacheEntry:
    """Holds a fully-downloaded chapter."""
    __slots__ = ("download_list", "folder_path", "expiry_time", "readers")

    def __init__(self, download_list: list, folder_path: str, expiry_time: float):
        self.download_list = download_list
        self.folder_path   = folder_path
        self.expiry_time   = expiry_time
        self.readers       = 0

    @property
    def expired(self) -> bool:
        return self.expiry_time < time.time()


class _PicEntry:
    """Holds the raw picture-URL list (before download)."""
    __slots__ = ("pictures", "expiry_time")

    def __init__(self, pictures: list, expiry_time: float):
        self.pictures    = pictures
        self.expiry_time = expiry_time

    @property
    def expired(self) -> bool:
        return self.expiry_time < time.time()


class _OrderState:
    """
    Tracks one in-flight order() call for a chapter_url.
    lock  – prevents duplicate downloads for the same URL.
    done  – signalled when order() finishes (success or fail).
    """
    __slots__ = ("lock", "done", "folder_path")

    def __init__(self):
        self.lock        = asyncio.Lock()
        self.done        = asyncio.Event()
        self.folder_path: Optional[str] = None


class _StorageEntry:
    """Generic key/value cache entry."""
    __slots__ = ("key", "value", "expiry_time", "readers")

    def __init__(self, key: str, value: Any, expiry_time: float):
        self.key         = key
        self.value       = value
        self.expiry_time = expiry_time
        self.readers     = 0

    def is_evictable(self) -> bool:
        return self.readers == 0 and self.expiry_time < time.time()


# --------------------------------------------------------------------- #
# ImageHandler
# --------------------------------------------------------------------- #

class ImageHandler:
    """
    Asyncio-safe cache of downloaded/converted chapter images.
    """

    __slots__ = (
        "_cache",          # chapter_url -> _CacheEntry
        "_pic_cache",      # chapter_url -> _PicEntry
        "_orders",         # chapter_url -> _OrderState
        "_storage",        # key          -> _StorageEntry
        "_pic_locks",      # chapter_url -> asyncio.Lock  (pic-list fetch)
        "_storage_locks",  # key          -> asyncio.Lock  (storage ops)
        "_global_lock",    # protects ALL structural mutations
        "_user_sm",        # user_id      -> asyncio.Semaphore
        "_user_sm_last",   # user_id      -> last-used timestamp
        "_bg_tasks",       # keeps references to fire-and-forget tasks
    )

    def __init__(self) -> None:
        self._cache:         dict[str, _CacheEntry]       = {}
        self._pic_cache:     dict[str, _PicEntry]         = {}
        self._orders:        dict[str, _OrderState]       = {}
        self._storage:       dict[str, _StorageEntry]     = {}
        self._pic_locks:     dict[str, asyncio.Lock]      = {}
        self._storage_locks: dict[str, asyncio.Lock]      = {}
        self._global_lock:   asyncio.Lock                 = asyncio.Lock()
        self._user_sm:       dict[str, asyncio.Semaphore] = {}
        self._user_sm_last:  dict[str, float]             = {}
        self._bg_tasks:      set[asyncio.Task]            = set()

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    @contextlib.asynccontextmanager
    async def _user_semaphore(self, user_id: str):
        user_id = str(user_id)

        async with self._global_lock:
            sem = self._user_sm.get(user_id)
            if sem is None:
                sem = asyncio.Semaphore(USER_LIMIT)
                self._user_sm[user_id] = sem
            self._user_sm_last[user_id] = time.time()

        async with sem:
            yield

    @staticmethod
    def _make_folder_path(
        webs: Any,
        chapter_url: str,
        data: Optional[dict],
        base_folder: str = "Process/Downloads",
    ) -> str:
        folder = f"{base_folder}/{type(webs).__name__}/"

        if data and (manga_title := data.get("manga_title")):
            title = data.get("title") or uuid.uuid4().hex[:8]
            folder += f"{manga_title}/{title}"
            if os.path.exists(folder):
                folder += f"_{uuid.uuid4().hex}"[:8]
                
        else:
            folder += uuid.uuid4().hex

        return folder

    @staticmethod
    async def _delete_folder(folder_path: Optional[str]) -> None:
        """Delete a folder off the event loop thread (never blocks the loop)."""
        if not folder_path:
            return
        try:
            await asyncio.to_thread(shutil.rmtree, folder_path, ignore_errors=True)
        except Exception as exc:
            logger.warning(f"Could not delete {folder_path}: {exc}")

    def _evict_prepare(self, chapter_url: str) -> Optional[str]:
        """
        Remove ALL in-memory state for chapter_url and return its folder
        path (or None). Caller MUST hold _global_lock. Does NOT touch disk -
        actual deletion happens afterwards, off-lock, via _delete_folder().
        """
        entry = self._cache.pop(chapter_url, None)
        self._pic_cache.pop(chapter_url, None)
        self._orders.pop(chapter_url, None)
        self._pic_locks.pop(chapter_url, None)
        return entry.folder_path if entry else None

    def _get_or_create_order(self, chapter_url: str) -> _OrderState:
        """
        Return existing (non-done) _OrderState or create a fresh one.
        Caller MUST hold _global_lock.
        """
        state = self._orders.get(chapter_url)
        if state is None or state.done.is_set():
            state = _OrderState()
            self._orders[chapter_url] = state

        return state

    def _get_or_create_pic_lock(self, chapter_url: str) -> asyncio.Lock:
        """Caller MUST hold _global_lock."""
        lock = self._pic_locks.get(chapter_url)
        if lock is None:
            lock = asyncio.Lock()
            self._pic_locks[chapter_url] = lock

        return lock

    def _get_or_create_storage_lock(self, key: str) -> asyncio.Lock:
        """Caller MUST hold _global_lock."""
        lock = self._storage_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._storage_locks[key] = lock

        return lock

    # ------------------------------------------------------------------ #
    # Generic storage cache
    # ----------------------------------------------------------------- #
    async def set_storage(self, key: str, value: Any) -> None:
        async with self._global_lock:
            self._get_or_create_storage_lock(key)
            self._storage[key] = _StorageEntry(key, value, time.time() + TIME_EXPIRE)

    async def get_storage(self, key: str) -> Optional[Any]:
        async with self._global_lock:
            entry = self._storage.get(key)
            if entry is None or entry.is_evictable():
                self._storage.pop(key, None)
                self._storage_locks.pop(key, None)
                return None

            entry.readers += 1
            return entry.value

    async def release_storage(self, key: str) -> None:
        """Decrement reader count; evict if expired and no readers remain."""
        async with self._global_lock:
            entry = self._storage.get(key)
            if entry is None:
                return

            entry.readers = max(0, entry.readers - 1)
            if entry.is_evictable():
                self._storage.pop(key, None)
                self._storage_locks.pop(key, None)

    async def pop_storage(self, key: str) -> None:
        """ Delete it when it is not needed """
        async with self._global_lock:
            self._storage.pop(key, None)
            self._storage_locks.pop(key, None)

        return

    # ------------------------------------------------------------------ #
    # Picture-URL cache
    # ------------------------------------------------------------------ #

    async def get_cache_pictures(
        self,
        webs: Any,
        chapter_url: str,
        data: Optional[dict] = None,
    ) -> Optional[list]:
        """
        Return raw picture-URL list, fetching from the web source if
        not cached or expired.
        """
        entry = self._pic_cache.get(chapter_url)
        if entry is not None and not entry.expired:
            return entry.pictures

        async with self._global_lock:
            lock = self._get_or_create_pic_lock(chapter_url)

        async with lock:
            for attempt in range(3):
                entry = self._pic_cache.get(chapter_url)
                if entry is not None and not entry.expired:
                    return entry.pictures

                self._pic_cache.pop(chapter_url, None)

                try:
                    pictures = await webs.get_pictures(chapter_url, data=data)
                except Exception as exc:
                    logger.error(
                        f"get_cache_pictures() attempt {attempt} failed "
                        f"for {chapter_url}: {exc}"
                    )
                    continue

                if pictures:
                    self._pic_cache[chapter_url] = _PicEntry(
                        pictures, time.time() + TIME_EXPIRE
                    )
                    return pictures

            return None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    async def order(
        self,
        user_id: str,
        webs: Any,
        chapter_url: str,
        data: Optional[dict] = None,
    ) -> None:
        """
        Download + convert images for chapter_url, cache the result,
        and signal any waiting get() callers.

        Spawn as a background task:
            asyncio.create_task(ihandler.order(webs, chapter_url, data))
        """
        existing = self._cache.get(chapter_url)
        if existing is not None and not existing.expired:
            return

        async with self._global_lock:
            existing = self._cache.get(chapter_url)
            if existing is not None and not existing.expired:
                return
            state = self._get_or_create_order(chapter_url)

        async with state.lock:
            async with self._global_lock:
                existing = self._cache.get(chapter_url)
                if existing is not None and not existing.expired:
                    return

            async with self._user_semaphore(user_id):
                try:
                    picture_list = await self.get_cache_pictures(webs, chapter_url, data)
                    if not picture_list:
                        return

                    if state.folder_path is None:
                        state.folder_path = self._make_folder_path(webs, chapter_url, data)

                    download_list: Optional[list] = None
                    for attempt in range(3):
                        try:
                            if getattr(webs, 'sb', False):
                                download_list = await download_images_sb(
                                    picture_list,
                                    download_dir=state.folder_path
                                )
                            else:
                                download_list = await download_and_convert_images(
                                    picture_list,
                                    base_url=webs.url,
                                    download_dir=state.folder_path,
                                )

                            break   # success – exit retry loop
                        except Exception as exc:
                            logger.warning(
                                f"download attempt {attempt} failed for {chapter_url}: {exc}"
                            )
                            await asyncio.sleep(0.8)

                    if not download_list:
                        logger.error(f"All download attempts failed for {chapter_url}")
                        await self._delete_folder(state.folder_path)
                        return

                    async with self._global_lock:
                        self._cache[chapter_url] = _CacheEntry(
                            download_list, state.folder_path, time.time() + TIME_EXPIRE
                        )
                except Exception as exc:
                    logger.exception(f"order() failed for {chapter_url}: {exc}")

                    async with self._global_lock:
                        self._pic_cache.pop(chapter_url, None)

                    await self._delete_folder(state.folder_path)

                finally:
                    state.done.set()

    async def get(
        self,
        chapter_url: str,
        timeout: float = _GET_TIMEOUT,
    ) -> list:
        async with self._global_lock:
            entry = self._cache.get(chapter_url)
            if entry is not None and not entry.expired:
                entry.readers += 1
                return entry.download_list

            state = self._orders.get(chapter_url)
            if state is None:
                return []

        if not state.done.is_set():
            try:
                await asyncio.wait_for(state.done.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"get() timed out after {timeout}s: {chapter_url}")
                return []

        async with self._global_lock:
            entry = self._cache.get(chapter_url)
            if entry is None or entry.expired:
                return []
            entry.readers += 1
            return entry.download_list

    async def release(self, chapter_url: str) -> None:
        folder_to_delete: Optional[str] = None

        async with self._global_lock:
            entry = self._cache.get(chapter_url)
            if entry is not None:
                entry.readers = max(0, entry.readers - 1)
                if entry.readers == 0 and entry.expired:
                    logger.info(f"Expiring chapter cache: {chapter_url}")
                    folder_to_delete = self._evict_prepare(chapter_url)

        if folder_to_delete:
            await self._delete_folder(folder_to_delete)

    async def force_release(self, chapter_url: str) -> None:
        """Immediately evict and delete downloaded chapter images from disk when readers reach 0."""
        folder_to_delete: Optional[str] = None

        async with self._global_lock:
            entry = self._cache.get(chapter_url)
            if entry is not None:
                entry.readers = max(0, entry.readers - 1)
                if entry.readers == 0:
                    logger.info(f"Force deleting chapter images from disk: {chapter_url}")
                    folder_to_delete = self._evict_prepare(chapter_url)

        if folder_to_delete:
            await self._delete_folder(folder_to_delete)

    # ------------------------------------------------------------------ #
    # Batch helpers
    # ------------------------------------------------------------------ #

    def order_batch(
        self,
        user_id: str,
        webs: Any,
        chapters: list[tuple[str, Optional[dict]]],
    ) -> None:
        """Pre-fetch multiple chapters in parallel (fire-and-forget)."""

        for chapter_url, chapter_data in chapters:
            task = asyncio.create_task(self.order(user_id, webs, chapter_url, chapter_data))
            self._bg_tasks.add(task)
            task.add_done_callback(self._bg_tasks.discard)

    async def get_batch(
        self,
        chapter_urls: list[str],
        timeout: float = _GET_TIMEOUT,
    ) -> list:
        """Get multiple chapters."""
        unique_urls = list(dict.fromkeys(chapter_urls))  # preserve order

        async def fetch_with_retry(url: str) -> list:
            for r in range(3):
                try:
                    p = await self.get(url, timeout)
                    if p:
                        return p
                except Exception:
                    pass

                if r < 2:
                    await asyncio.sleep(0.2)

            raise RuntimeError(f"Missing chapter data for URL: {url}")

        tasks = [asyncio.create_task(fetch_with_retry(url)) for url in unique_urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        error = next((r for r in results if isinstance(r, BaseException)), None)
        if error is not None:
            successful_urls = [
                url for url, r in zip(unique_urls, results)
                if not isinstance(r, BaseException)
            ]
            if successful_urls:
                await self.release_batch(successful_urls)
            
            raise error

        return results

    async def release_batch(self, chapter_urls: list[str], force: bool = False) -> None:
        """Release multiple chapters concurrently, immediately deleting from disk if force=True."""

        await asyncio.gather(
            *(self.force_release(url) if force else self.release(url) for url in chapter_urls),
            return_exceptions=True,
        )

    # ------------------------------------------------------------------ #
    # Maintenance
    # ------------------------------------------------------------------ #

    async def purge_expired(self) -> int:
        now = time.time()
        folders_to_delete: list[str] = []

        async with self._global_lock:
            dead_chapters = [
                url for url, entry in self._cache.items()
                if entry.expiry_time < now and entry.readers == 0
            ]
            for url in dead_chapters:
                fp = self._evict_prepare(url)
                if fp:
                    folders_to_delete.append(fp)

            dead_pics = [
                url for url, entry in self._pic_cache.items()
                if entry.expiry_time < now and url not in self._cache
            ]
            for url in dead_pics:
                self._pic_cache.pop(url, None)
                self._pic_locks.pop(url, None)

            dead_orders = [
                url for url, state in self._orders.items()
                if state.done.is_set()
                and url not in self._cache
                and url not in self._pic_cache
            ]
            for url in dead_orders:
                self._orders.pop(url, None)

            dead_storage = [
                k for k, entry in self._storage.items()
                if entry.is_evictable()
            ]
            for k in dead_storage:
                self._storage.pop(k, None)
                self._storage_locks.pop(k, None)


            idle_users = [
                uid for uid, last in self._user_sm_last.items()
                if now - last > _USER_SEM_IDLE_TTL
                and getattr(self._user_sm.get(uid), "_value", 0) == USER_LIMIT
            ]
            for uid in idle_users:
                self._user_sm.pop(uid, None)
                self._user_sm_last.pop(uid, None)

        if folders_to_delete:
            await asyncio.gather(
                *(self._delete_folder(fp) for fp in folders_to_delete),
                return_exceptions=True,
            )

        return len(dead_chapters)

    async def cleanup(self) -> None:
        """Force cleanup of all resources (graceful shutdown)."""
        folders_to_delete: list[str] = []

        async with self._global_lock:
            for url in list(self._cache.keys()):
                fp = self._evict_prepare(url)
                if fp:
                    folders_to_delete.append(fp)

            count = len(self._cache) + len(folders_to_delete)  # informational
            self._pic_cache.clear()
            self._orders.clear()
            self._pic_locks.clear()
            self._storage.clear()
            self._storage_locks.clear()

        if folders_to_delete:
            await asyncio.gather(
                *(self._delete_folder(fp) for fp in folders_to_delete),
                return_exceptions=True,
            )

        logger.info(f"Cleaned up {len(folders_to_delete)} cached chapters")


# =====================================================
ihandler = ImageHandler()
# =====================================================

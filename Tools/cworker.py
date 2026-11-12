# Code By @V_Sbotmaker (on Telegram)
from typing import Optional, Dict
from pyrogram.errors import (
    FileReferenceEmpty,
    FileReferenceExpired,
    FileReferenceInvalid,
    UsernameInvalid,
)
import pyrogram.errors as pes

from TG.storage import retry_on_flood, igrone_error, queue
from bot import Bot, Vars, logger


from Tools.img2cbz import images_to_cbz
from Tools.img2pdf import (
    download_and_convert_images,
    convert_images_to_pdf_async,   # semaphore-guarded async wrapper
    ImageDownloadError,
)

import os
import shutil
import asyncio
import gc

from time import time
from pyrogram.types import InputMediaDocument

from Tools.base import TaskCard, database
from .uploaders import get_target_auto_channel, Uploader
from Tools.user_clients import user_client_manager
from .ihandler import ihandler

# ── Upload concurrency cap ──────────────────────────────────────────────────
_UPLOAD_CONCURRENT = int(os.environ.get("UPLOAD_CONCURRENT", "10"))
_upload_sem: Optional[asyncio.Semaphore] = None


def _get_upload_sem() -> asyncio.Semaphore:
    global _upload_sem
    if _upload_sem is None:
        _upload_sem = asyncio.Semaphore(_UPLOAD_CONCURRENT)
    return _upload_sem

# ============================================
# Per-user Worker Pool Configuration
# ============================================

# Kitne workers ek user ke liye concurrent chalenge (2-3 recommended)
WORKERS_PER_USER: int = getattr(Vars, "WORKERS_PER_USER", 2)

# Kitne seconds idle rehne ke baad worker terminate hoga
WORKER_IDLE_TIMEOUT: int = 30

# Global registry: user_id (str) -> UserWorkerPool
_user_pools: Dict[str, "UserWorkerPool"] = {}
_user_upload_locks: Dict[str, asyncio.Lock] = {}

def _get_user_upload_lock(user_id: str) -> asyncio.Lock:
    user_id = str(user_id)
    if user_id not in _user_upload_locks:
        _user_upload_locks[user_id] = asyncio.Lock()
    return _user_upload_locks[user_id]
# Lock is created lazily inside get_or_create_pool (needs a running event loop)

LOGS_MESSAGE = """
{caption}

{url}

`Downloaded By`: `{user_id}`  [{mention}]
`PDF Password`: `{password}`
`Time Taken`: `{time_taken}`
`File Taken`: `{file_taken}`"""


class NormalError(BaseException):
    def __init__(self):
        pass


async def send_error(task_card: TaskCard, error_text):
    if task_card.sts:
        docs = await retry_on_flood(task_card.sts.edit)(
            f"{task_card.url} : {task_card.status} -> `{error_text}`"
        )
    else:
        docs = await retry_on_flood(Bot.send_message)(
            int(task_card.user_id), f"{task_card.url} : {task_card.status} -> `{error_text}`"
        )

    await retry_on_flood(docs.copy)(Vars.LOG_CHANNEL) if Vars.LOG_CHANNEL else None


# create_file_async kept for CBZ (img2cbz is a simple sync function).
def create_file_async(process):
    """Async wrapper for File creation"""
    async def wrapper(*args, **kwargs):
        return await asyncio.to_thread(
            process, *args, **kwargs
        )
    return wrapper


def clean_system(tasks_card: TaskCard, thumb: str, values: list):
    """Clean up files and directories based on task settings."""

    def safe_remove(path):
        """Safely remove file or directory."""
        if not path or not isinstance(path, str):
            return

        try:
            if os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)
            elif os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
        except Exception:
            pass

    if thumb and isinstance(thumb, str):
        safe_remove(thumb)

    for value in values:
        if value:
            safe_remove(value)

    if tasks_card and getattr(tasks_card, "main_dir", None):
        safe_remove(tasks_card.main_dir)

    if tasks_card and getattr(tasks_card, "user_id", None):
        if queue.check_queue(tasks_card.user_id) is False:
            process_dir = f"Process/{tasks_card.user_id}"
            safe_remove(process_dir)
    


async def copy_media(channel_id, doc, caption, client=None):
    _bot = client or Bot
    try:
        await retry_on_flood(_bot.copy_media_group)(
            channel_id,
            doc[-1].chat.id,
            doc[-1].id,
            captions=caption,
        )
    except Exception:
        try:
            await retry_on_flood(_bot.copy_message)(
                channel_id, doc[-1].chat.id, doc[-1].id, caption=caption
            )
        except UsernameInvalid:
            pass
        except pes.exceptions.bad_request_400.ChannelInvalid:
            pass

        except Exception as e:
            logger.exception(f"Error copying media: {e}")



PICTURES_ERROR_MSG = """
<blockquote><b>Error at Downloading Picture </b></blockquote>

<blockquote><b>Check The Picture Link, Bot cannot download the paid pictures and the pictures which are not available in the website.

Contact @WizardBotHelper for Help </b></blockquote>"""

def check_and_return(file_path: Optional[str] = None) -> Optional[str]:
    try:
        return file_path if file_path and os.path.exists(file_path) else None
    except Exception:
        return None


async def send_manga_chapter(tasks_card: TaskCard):
    start_time = time()
    error_msg = None

    pdf_output_path = None
    cbz_output_path = None
    #download_dir = None
    #compressed_dir = None
    password = None
    thumb = None 
    media_docs = []

    loop = asyncio.get_running_loop()
    try:
        # ============================================
        # STEP 1 - Parallel: banner + settings
        # ============================================
        tasks_card.status = "Fecting Info"
        downloads_tasks = loop.create_task(tasks_card.get_images_paths())
        
        banner_setting, user_settings = await asyncio.gather(
            tasks_card.get_banner(),
            #tasks_card.processsing,
            database.get_settings(tasks_card.user_id),
            return_exceptions=True,
        )
        
        # Handle exceptions from gather
        if not isinstance(banner_setting, dict):
            banner_setting = {}

        tasks_card.status = "Extracting Banners"
        
        thumb = check_and_return(banner_setting.get("thumb_file_name"))
        banner1 = check_and_return(banner_setting.get("banner1_file_path"))
        banner2 = check_and_return(banner_setting.get("banner2_file_path"))

        # ============================================
        # STEP 2 - File naming 
        # ============================================
        tasks_card.status = "File Naming"
        file_name_template = (
            tasks_card.setting.get("file_name")
            or "Chapter {episode_number} {manga_title}"
        )

        if tasks_card.webs.sf == "mf" and any(
            x in tasks_card.manga_title for x in ("Vol", "Volume")
        ):
            file_name_template = file_name_template.replace("Chapter", "Vol")

        ep_num = str(tasks_card.episode_number)

        # Build both names in one pass
        file_name = (
            file_name_template.replace("{episode_number}", ep_num)
            .replace("{chapter_num}", ep_num)
            .replace("{manga_title}", tasks_card.manga_title)
        )

        full_file_name = (
            file_name_template.replace("{episode_number}", ep_num)
            .replace("{chapter_num}", ep_num)
            .replace("{manga_title}", tasks_card.orginal_manga_title)
        )

        caption_template = (
            tasks_card.setting.get("caption") or "<blockquote>{file_name}</blockquote>"
        )

        caption = (
            caption_template.replace("{file_name}", full_file_name)
            .replace("{episode_number}", ep_num)
            .replace("{chapter_num}", ep_num)
            .replace("{manga_title}", tasks_card.orginal_manga_title)
        )

        # ============================================
        # STEP 3 - Convert PDF/CBZ in parallel
        # ============================================
        tasks_card.status = f"Downloading Images "
        downloads_list = await asyncio.gather(
            downloads_tasks, 
            return_exceptions=True
        )
        if downloads_list and len(downloads_list) == 1:
            downloads_list = downloads_list[0]
            
        if not isinstance(downloads_list, list):
            await igrone_error(send_error)(tasks_card, PICTURES_ERROR_MSG)
            raise NormalError()

        
        tasks_card.status = f"Converting {len(downloads_list)} Images"
        file_time = time()
        
        await igrone_error(tasks_card.sts.edit)(
            "<code>Converting.....</code>"
        ) if tasks_card.sts else None

        file_type = tasks_card.setting.get("type") or ["PDF"]
        if not file_type:
            file_type = ["PDF"]

        processing_tasks = []

        if "PDF" in file_type:
            pdf_output_path = f"{tasks_card.main_dir}/{file_name}.pdf"
            password = tasks_card.setting.get("password")

            try:
                compress = int(tasks_card.setting.get("compress", 80))
            except (ValueError, TypeError):
                compress = 80

            compress = compress or 80
            hyperLink = tasks_card.setting.get("hyper")

            # convert_images_to_pdf_async acquires the global PDF semaphore
            # internally — no extra wrapping needed here.
            processing_tasks.append(
                convert_images_to_pdf_async(
                    image_files=downloads_list,
                    pdf_output_path=pdf_output_path,
                    compressed_dir=tasks_card.compressed_dir,
                    password=password,
                    compression_quality=compress,
                    hyperLink=hyperLink,
                    banner1=banner1,
                    banner2=banner2,
                )
            )

        if "CBZ" in file_type:
            cbz_output_path = f"{tasks_card.main_dir}/{file_name}.cbz"
            os.makedirs(os.path.dirname(cbz_output_path), exist_ok=True)
            processing_tasks.append(
                create_file_async(images_to_cbz)(downloads_list, cbz_output_path)
            )

        results = await asyncio.gather(*processing_tasks, return_exceptions=True)
        tasks_card.status = "Checking Issue"
        for result in results:
            if result is not None:
                #logger.exception(f"Error processing task: {result}")
                await igrone_error(send_error)(tasks_card, str(result))
                raise NormalError()

        file_end_time = time() - file_time
        # ============================================
        # STEP 4 - Build media docs
        # ============================================
        tasks_card.status = "Uploading"
        await igrone_error(tasks_card.sts.edit)(
            "<code>Uploading.....</code>"
        ) if tasks_card.sts else None
        
        if pdf_output_path and os.path.exists(pdf_output_path):
            media_docs.append(
                InputMediaDocument(pdf_output_path, caption=caption, thumb=thumb)
            )

        if cbz_output_path and os.path.exists(cbz_output_path):
            media_docs.append(
                InputMediaDocument(cbz_output_path, caption=caption, thumb=thumb)
            )

        if not media_docs:
            await igrone_error(send_error)(tasks_card, "No File Type Found")
            raise NormalError()

        # ============================================
        # STEP 5 - Upload + get user info at same time
        # ============================================
        _usem = _get_upload_sem()

        async with _get_user_upload_lock(tasks_card.user_id):
            async with user_client_manager.get_client_ctx(tasks_card.user_id) as user_client:
                upload_client = user_client or Bot

            async with _usem:
                doc, user = await asyncio.gather(
                    retry_on_flood(upload_client.send_media_group)(int(tasks_card.chat_id), media_docs),
                    igrone_error(Bot.get_users)(int(tasks_card.user_id))
                    if Vars.LOG_CHANNEL
                    else asyncio.sleep(0),
                    return_exceptions=True,
                )

            if isinstance(doc, Exception):
                raise doc

            # ============================================
            # STEP 6 - Auto forward + dump + log all at once
            # ============================================
            tasks_card.status = "Targeting"
            await igrone_error(tasks_card.sts.edit)(
                "<code>Uploading to targets.....</code>"
            ) if tasks_card.sts else None

            dump = tasks_card.setting.get("dump", None)
            try:
                dump = int(str(dump))
            except (TypeError, ValueError):
                dump = None

            time_taken = time() - start_time
            minutes, seconds = divmod(int(time_taken), 60)

            # Determine mode
            mode_str = "Auto" if getattr(tasks_card, "update_mode", False) else "Manual"

            # Determine worker bot info
            connect_bot_str = "Main Bot"
            if upload_client != Bot:
                try:
                    me = getattr(upload_client, "me", None) or await upload_client.get_me()
                    if me and getattr(me, "username", None):
                        connect_bot_str = f"@{me.username}"
                    elif me:
                        connect_bot_str = str(me.id)
                except Exception:
                    connect_bot_str = "Worker Bot"
            else:
                try:
                    me = getattr(Bot, "me", None) or await Bot.get_me()
                    if me and getattr(me, "username", None):
                        connect_bot_str = f"@{me.username}"
                except Exception:
                    connect_bot_str = "Main Bot"

            # Determine upload channel invite link (only used in Auto mode)
            upload_channel_link = None
            if mode_str == "Auto" and str(tasks_card.chat_id).startswith("-100"):
                try:
                    chat_obj = await upload_client.get_chat(int(tasks_card.chat_id))
                    upload_channel_link = getattr(chat_obj, "invite_link", None)
                    if not upload_channel_link:
                        try:
                            upload_channel_link = await upload_client.export_chat_invite_link(int(tasks_card.chat_id))
                        except Exception:
                            pass
                except Exception:
                    pass

                if not upload_channel_link:
                    upload_channel_link = getattr(doc[-1], "link", None)
                    if not upload_channel_link:
                        cid = str(tasks_card.chat_id)
                        upload_channel_link = f"https://t.me/c/{cid[4:]}/{doc[-1].id}"

            user_mention = user.mention() if (user and not isinstance(user, Exception) and hasattr(user, "mention")) else "[.]"

            # Build formatted caption text ONLY (No media sent/forwarded to log channel)
            log_text = (
                f"{full_file_name}\n\n"
                f"{tasks_card.url}\n\n"
                f"Downloaded By: {tasks_card.user_id}  [{user_mention}]\n"
                f"PDF Password: {password or 'None'}\n"
                f"Time Taken: {minutes}m, {seconds}s\n"
                f"File Taken: {file_end_time:.2f}s\n"
                f"Mode = {mode_str}\n"
                f"Connect Bot = {connect_bot_str}"
            )
            if mode_str == "Auto" and upload_channel_link:
                log_text += f"\nUpload channel link = {upload_channel_link}"

            post_tasks = []
            if Vars.AUTO_F:
                post_tasks.append(
                    Uploader().upload_to_targets_channels(
                        doc[-1],
                        original_ep_num=str(tasks_card.episode_number),
                        search_name=tasks_card.orginal_manga_title,
                        user_id=str(tasks_card.user_id),
                        client=upload_client,
                    )
                )

            if Vars.CONSTANT_DUMP_CHANNEL:
                post_tasks.append(copy_media(Vars.CONSTANT_DUMP_CHANNEL, doc, caption, client=upload_client))

            if dump:
                post_tasks.append(copy_media(dump, doc, caption, client=upload_client))

            if Vars.LOG_CHANNEL:
                # Requirement 1: Send ONLY formatted text message to LOG_CHANNEL (No file)
                post_tasks.append(
                    retry_on_flood(Bot.send_message)(
                        Vars.LOG_CHANNEL,
                        log_text,
                        disable_web_page_preview=True,
                    )
                )

            if post_tasks:
                await asyncio.gather(*post_tasks, return_exceptions=True)

    except NormalError:
        error_msg = True

    except ImageDownloadError:
        error_msg = True

        await igrone_error(send_error)(
            tasks_card, PICTURES_ERROR_MSG
        )
        target = tasks_card.sts or None
        if target:
            await retry_on_flood(target.edit_text)(PICTURES_ERROR_MSG)
        else:
            await retry_on_flood(Bot.send_message)(int(tasks_card.user_id), PICTURES_ERROR_MSG)

    except (
        FileReferenceExpired,
        FileReferenceEmpty,
        FileReferenceInvalid,
        pes.exceptions.bad_request_400.FileReferenceExpired,
    ):
        error_msg = True
        msg = "<b><i>Change Your Thumb or Banner and Try Again...</i></b>"
        target = tasks_card.sts or None
        if target:
            await retry_on_flood(target.edit_text)(msg)
        else:
            await retry_on_flood(Bot.send_message)(int(tasks_card.user_id), msg)

    except Exception as e:
        error_msg = True
        logger.exception(f"Error processing task: {e}")

        await igrone_error(send_error)(tasks_card, str(e))
        

    finally:
        tasks_card.status = "Deleting"
        clean_system(
            tasks_card,
            str(thumb),
            [pdf_output_path, cbz_output_path, tasks_card.compressed_dir, tasks_card.main_dir],
        )
        
        await ihandler.release_batch(tasks_card.chapters_urls)
        await ihandler.release_storage(tasks_card.poster)
        
        if not error_msg:
            await igrone_error(tasks_card.sts.delete)() if tasks_card.sts else None

        try:
            if not queue.check_poster(tasks_card.poster):
                await ihandler.pop_storage(tasks_card.poster)
                if thumb and os.path.exists(str(thumb)):
                    await asyncio.to_thread(lambda: os.remove(str(thumb)))
        except Exception:
            pass 
        
        await tasks_card.close()



# ============================================
# Shared Worker Pool
# ============================================

class SharedWorkerPool:
    def __init__(self, num_workers: int = 15):
        self.num_workers = num_workers
        self._workers: list = []
        self._wake_event = asyncio.Event()

    def start(self) -> None:
        self._workers = [
            asyncio.create_task(
                self._worker_loop(i),
                name=f"shared-worker-{i}",
            )
            for i in range(self.num_workers)
        ]
        logger.info(f"[SharedWorkerPool] {self.num_workers} shared workers started")

    def wake(self) -> None:
        self._wake_event.set()

    def stop(self) -> None:
        for w in self._workers:
            w.cancel()

    async def _worker_loop(self, worker_index: int) -> None:
        wid = f"shared={worker_index}"
        logger.info(f"[Worker] {wid} started")

        try:
            while True:
                result = queue.get_next_shared_task()

                if result is None:
                    self._wake_event.clear()
                    try:
                        await asyncio.wait_for(
                            self._wake_event.wait(),
                            timeout=60,
                        )
                        continue
                    except asyncio.TimeoutError:
                        continue

                tasks_card, _ = result
                logger.info(f"[Worker] {wid} processing task {tasks_card.tasks_id}")

                tasks_card.status = "Processing"
                if tasks_card.sts:
                    await igrone_error(tasks_card.sts.edit)("<code>Processing.....</code>")

                try:
                    await send_manga_chapter(tasks_card)
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    logger.exception(f"[Worker] {wid} error: {err}")
                    await igrone_error(send_error)(tasks_card, str(err))
                finally:
                    await queue.task_done(tasks_card)

        except asyncio.CancelledError:
            logger.info(f"[Worker] {wid} cancelled")

_shared_pool: Optional[SharedWorkerPool] = None

# ============================================
# Per-User Worker Pool
# ============================================


class UserWorkerPool:
    """
    Ek user ke liye dedicated worker pool.

    - `num_workers` workers spawn hote hain jab pool start hota hai.
    - Har worker sirf us user ke tasks process karta hai.
    - Agar `WORKER_IDLE_TIMEOUT` seconds tak koi task nahi milta,
      worker automatically exit kar leta hai.
    - Jab sab workers exit ho jaate hain, pool khud ko
      global registry se remove kar leta hai.
    """

    def __init__(self, user_id: str, num_workers: int = 2):
        self.user_id     = user_id
        self.num_workers = num_workers
        self._workers: list = []   # asyncio.Task objects
        self._wake_event = asyncio.Event()

    # ── lifecycle ─────────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn all workers as asyncio Tasks."""
        self._workers = [
            asyncio.create_task(
                self._worker_loop(i),
                name=f"user-{self.user_id}-worker-{i}",
            )
            for i in range(self.num_workers)
        ]
        logger.info(
            f"[WorkerPool] User {self.user_id}: {self.num_workers} workers started"
        )

    def wake(self) -> None:
        """Signal workers that a new task is available."""
        self._wake_event.set()

    def is_alive(self) -> bool:
        """True if at least one worker is still running."""
        return any(not w.done() for w in self._workers)

    def stop(self) -> None:
        """Cancel all workers immediately."""
        for w in self._workers:
            w.cancel()

    # ── internal worker loop ──────────────────────────────────────────────

    async def _worker_loop(self, worker_index: int) -> None:
        """
        Ek single worker loop:
        - Apne user ka next pending task uthata hai.
        - Agar idle timeout ke baad bhi koi task nahi, exit karta hai.
        - Exit hone par, agar koi bhi worker nahi bacha,
          pool ko global registry se remove karta hai.
        """
        wid = f"user={self.user_id} w={worker_index}"
        logger.info(f"[Worker] {wid} started")

        try:
            while True:
                # ── task fetch ──────────────────────────────────────────────
                result = queue.get_user_task(
                    self.user_id, max_concurrent=WORKERS_PER_USER
                )

                if result is None:
                    # No task available – wait for wake signal or timeout
                    self._wake_event.clear()
                    try:
                        await asyncio.wait_for(
                            self._wake_event.wait(),
                            timeout=WORKER_IDLE_TIMEOUT,
                        )
                        # Got woken up, try again immediately
                        continue
                    except asyncio.TimeoutError:
                        # Idle timeout hit – check once more before exiting
                        result = queue.get_user_task(
                            self.user_id, max_concurrent=WORKERS_PER_USER
                        )
                        if result is None:
                            logger.info(
                                f"[Worker] {wid} idle timeout – exiting"
                            )
                            return  # Worker exit

                tasks_card, _ = result
                logger.info(
                    f"[Worker] {wid} processing task {tasks_card.tasks_id}"
                    f" – {tasks_card.manga_title} {tasks_card.episode_number}"
                )

                # ── process ─────────────────────────────────────────────────
                tasks_card.status = "Processing"
                if tasks_card.sts:
                    await igrone_error(tasks_card.sts.edit)(
                        "<code>Processing.....</code>"
                    )

                try:
                    await send_manga_chapter(tasks_card)
                except asyncio.CancelledError:
                    raise  # propagate so the worker task exits cleanly
                except Exception as err:
                    logger.exception(f"[Worker] {wid} error: {err}")
                    await igrone_error(send_error)(tasks_card, str(err))
                finally:
                    await queue.task_done(tasks_card)

        except asyncio.CancelledError:
            logger.info(f"[Worker] {wid} cancelled")

        finally:
            # Cleanup: remove pool from global registry when all workers done
            await _cleanup_pool_if_dead(self.user_id)


# ============================================
# Pool registry helpers
# ============================================

_pools_lock_obj: Optional[asyncio.Lock] = None


def _get_pools_lock() -> asyncio.Lock:
    """Lazy-init the asyncio.Lock (must be created inside a running loop)."""
    global _pools_lock_obj
    if _pools_lock_obj is None:
        _pools_lock_obj = asyncio.Lock()
    return _pools_lock_obj


async def _cleanup_pool_if_dead(user_id: str) -> None:
    """Remove pool from registry if no workers are alive."""
    lock = _get_pools_lock()
    async with lock:
        pool = _user_pools.get(user_id)
        if pool and not pool.is_alive():
            _user_pools.pop(user_id, None)
            logger.info(
                f"[WorkerPool] User {user_id}: pool removed from registry"
            )


async def get_or_create_pool(user_id: str) -> UserWorkerPool:
    """
    Return the existing (alive) pool for *user_id*, or create+start a new one.
    """
    lock = _get_pools_lock()
    async with lock:
        pool = _user_pools.get(user_id)
        if pool and pool.is_alive():
            return pool

        pool = UserWorkerPool(user_id, num_workers=WORKERS_PER_USER)
        _user_pools[user_id] = pool
        pool.start()
        return pool


from config import Vars
async def notify_user_task(user_id: str) -> None:
    """
    Jab queue mein ek nayi task add ho, is function ko call karo.
    Yeh us user ka pool create/wake karta hai (if shared workers not used).
    """
    if getattr(Vars, 'USE_SHARED_WORKERS', False):
        global _shared_pool
        if _shared_pool is None:
            _shared_pool = SharedWorkerPool(num_workers=15)
            _shared_pool.start()
        _shared_pool.wake()
    else:
        pool = await get_or_create_pool(user_id)
        pool.wake()

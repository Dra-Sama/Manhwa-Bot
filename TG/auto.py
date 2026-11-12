# Code By @V_Sbotmaker (on Telegram)
import string
import random
import asyncio
import gc

from Tools.db import database, get_episode_number
from Tools.base import TaskCard, retry_on_flood, igrone_error
from bot import Bot, Vars, logger
from pyrogram import filters
from .storage import get_webs, check_get_web, queue, iter_chapters
from typing import AsyncGenerator
from pyrogram.errors import UserIsBlocked, PeerIdInvalid
from math import floor
from functools import lru_cache
from Tools.ihandler import ihandler

# ============================================
# Bounded queue: prevents unbounded RAM growth when the update sweep
# is faster than the picture_queue consumer (update_worker).
picture_queue = asyncio.Queue(maxsize=200)
# ============================================




@lru_cache(maxsize=512)
def _cached_episode_number(title: str):
    return get_episode_number(title)


def _safe_float(val) -> float:
    try:
        return float(int(val))
    except (TypeError, ValueError):
        return -1.0


# ============================================
# Fixed check_chapter_ - removed dead code
# ============================================
def check_chapter_(
    chapter: dict,
    db_lastest_title: str,
    db_lastest_num: float
) -> bool:
    try:
        if not db_lastest_title:
            return False

        chapter_title = chapter.get("title", "")
        if not chapter_title:
            return False

        # Single combined title check
        if chapter_title == db_lastest_title or chapter_title in db_lastest_title:
            return False

        web_latest = _cached_episode_number(chapter_title)
        if web_latest is None:
            return False

        web_latest = _safe_float(web_latest)
        if web_latest < 0:
            return False

        return web_latest > db_lastest_num

    except Exception as er:
        logger.exception(f"Error in check_chapter_: {er}")
        return False


# ============================================
# Get web class
# ============================================
def get_web_class(web_sf: str, manga_url: str):
    try:
        web_class = get_webs(web_sf) or check_get_web(manga_url)
        return web_class
    except Exception as e:
        logger.exception(f"Error in get_web_class: {e}")
    return None


from Webs.source_manager import execute_source_with_retry

# ============================================
# Get chapters
# ============================================
async def get_chapters(web_class, manga_data: dict, manga_url: str, user_id: str = None) -> list:
    try:
        sf = getattr(web_class, "sf", "")
        name = getattr(web_class, "name", type(web_class).__name__)

        manga_data_res = await execute_source_with_retry(
            sf,
            name,
            manga_url,
            web_class.get_chapters,
            manga_data,
            user_id=user_id,
        )
        if not manga_data_res:
            return []

        manga_data = manga_data_res
        
        # Fix: hasattr() only takes 2 arguments, not 3
        if hasattr(web_class, 'iter_chapters'):
            chapters = web_class.iter_chapters(manga_data)
        else:
            chapters = iter_chapters(manga_data)
        
        if not chapters:
            return []

        return [
            {**chapter, "manga_url": manga_url}
            for chapter in chapters
            if isinstance(chapter, dict)
        ]
    except Exception:
        return []


# ============================================
# Filter - pre-compute episode numbers
# ============================================
def filter_by_episode_(data: list, max_episode: float) -> list:
    result = []
    for item in data:
        title = item.get("title", "")
        if not title:
            continue
        
        ep_num = _cached_episode_number(title)
        if ep_num is None:
            continue
        try:
            n = float(ep_num) if '.' in str(ep_num) else int(ep_num)
            if n > max_episode:
                result.append(item)
        except (TypeError, ValueError):
            continue
    return result


# ============================================
# Process chapter - pre-compute all numbers once
# ============================================
async def process_chapter(
    web_list: list, web_sf: str, user_id: str = None
) -> AsyncGenerator[tuple, None]:
    for manga_data in web_list:
        updated_nu = set()

        manga_url = manga_data.get("url")
        if not manga_url:
            continue

        web_class = get_web_class(web_sf, manga_url)
        if not web_class:
            continue

        try:
            chapters = await get_chapters(
                web_class=web_class,
                manga_data=manga_data,
                manga_url=manga_url,
                user_id=user_id,
            )
            if not chapters:
                continue

            first_chapter = chapters[0]
            first_title = first_chapter.get("title")
            if not first_title:
                continue

            db_latest_title = manga_data.get("lastest_chapter")
            logger.info(f"DB latest: {db_latest_title}, Web latest: {first_title}")

            # No DB record - yield latest
            if not db_latest_title:
                yield first_chapter, web_class
                continue

            # Title match check
            if (first_title == db_latest_title or
                first_title in db_latest_title or
                db_latest_title in first_title):
                continue

            # Parse numbers ONCE
            db_num_raw = _cached_episode_number(db_latest_title)
            if not db_num_raw:
                yield first_chapter, web_class
                continue

            db_num = _safe_float(db_num_raw)
            if db_num < 0:
                yield None, None
                continue

            first_num = _safe_float(
                _cached_episode_number(first_title) or -1
            )

            if first_num < 0 or first_num == db_num:
                continue

            # Filter new chapters
            new_chapters = filter_by_episode_(chapters, db_num)
            for chapter in new_chapters:
                try:
                    ch_title = chapter.get("title", "")
                    num = _safe_float(
                        _cached_episode_number(ch_title) or -1
                    )
                    if num not in updated_nu and num > db_num:
                        updated_nu.add(num)
                        yield chapter, web_class
                except Exception as er:
                    logger.exception(f"Error in chapter loop: {er}")

        except Exception as er:
            logger.exception(f"Error processing manga: {er}")


        
# ============================================
# Process web - chunk processing
# ============================================
async def process_web(
    web_sf: str,
    web_list: list,
    batch_size: int = 5,
    user_id: str = None,
) -> AsyncGenerator:
    try:
        # Use web_sf string as key - reliable hashing
        update_batch: list = []

        async for update_manga, web_class in process_chapter(
            web_list=web_list, web_sf=web_sf, user_id=user_id
        ):
            if not update_manga or not web_class:
                continue

            update_batch.append((update_manga, web_class))

            if len(update_batch) >= batch_size:
                yield web_class, [m for m, _ in update_batch]
                update_batch.clear()

        # Yield remaining
        if update_batch:
            web_class = update_batch[0][1]
            yield web_class, [m for m, _ in update_batch]

    except Exception as er:
        logger.error(f"Error in process_web: {er}")


# ============================================
# Process user - parallel web processing
# ============================================
async def process_user(user_data: dict) -> int:
    update_count = 0

    user_id = user_data.get("_id")
    if not user_id:
        return update_count

    subs_data: dict = user_data.get("subs", {})
    if not subs_data:
        return update_count

    chat_id = str(user_id)

    if Vars.IS_PRIVATE and chat_id == "shared_admin_subs":
        chat_id = str(Vars.ADMINS[0])
    elif user_id == "shared_admin_subs":
        return update_count

    # Get user mention
    user_mention = f"<code>{chat_id}</code>"
    try:
        user = await Bot.get_users(int(chat_id))
        if not isinstance(user, list):
            user_mention = f"<code>{chat_id}</code> [{user.mention()}]"
    except Exception:
        pass

    # Process all webs concurrently
    async def process_one_web(web_sf, web_list):
        count = 0
        if not web_list:
            return count

        if not await database.is_source_available(chat_id, web_sf):
            logger.info(f"Source {web_sf} is disabled for user {chat_id}. Skipping.")
            return count

        async for web_class, update_manga in process_web(
            web_sf=web_sf, web_list=web_list, user_id=chat_id
        ):
            if not update_manga:
                continue

            await picture_queue.put(
                (web_class, chat_id, update_manga, user_mention)
            )
            count += len(update_manga)
        
        return count

    # Run all webs at same time
    tasks = [
        process_one_web(web_sf, web_list)
        for web_sf, web_list in subs_data.items()
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    update_count = sum(r for r in results if isinstance(r, int))
    return update_count


# ============================================
# get_updates_users - batch user processing
# ============================================
async def get_updates_users() -> None:
    loop = asyncio.get_running_loop()
    logger.debug("Starting get_updates_users")

    semaphore = asyncio.Semaphore(5)  # max 5 users at once

    async def process_one(user_data):
        async with semaphore:
            try:
                await process_user(user_data)
            except Exception as er:
                logger.exception(f"Error processing user: {er}")

    tasks = []
    try:
            async for user_data in database.get_all_subs():
                uid = user_data.get('_id', 'N/A')
                logger.info(f"Queuing user {uid}")
                tasks.append(loop.create_task(process_one(user_data)))

                # Chunk tasks to prevent RAM explosion
                if len(tasks) >= 5:
                    await asyncio.gather(*tasks, return_exceptions=True)
                    tasks.clear()
    except Exception as er:
            logger.exception(f"Error iterating subs: {er}")

    if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    logger.debug(f"Finished update cycle")










# ============================================
# send_message
# ============================================
async def send_message(user_id, message, retries: int = 3):
    for attempt in range(retries):
        try:
            sts = await retry_on_flood(Bot.send_message)(
                chat_id=int(user_id), text=message
            )
            return sts

        except (UserIsBlocked, PeerIdInvalid):
            await database.delete_user(user_id)
            return None

        except ConnectionError:
            wait = 10 * (attempt + 1)
            logger.warning(f"Connection error, retry {attempt+1}/{retries} in {wait}s")
            await asyncio.sleep(wait)

        except Exception as er:
            logger.exception(f"Error sending to {user_id}: {er}")
            return None

    return None


# ============================================
# process_pictures - with retry
# ============================================

async def process_pictures(web_class, chapter: dict) -> list:
    if isinstance(web_class, str):
        web_class = get_webs(web_class)

    for attempt in range(3):
        try:
            pictures = await ihandler.get_cache_pictures(
                web_class, chapter_url=str(chapter.get("url")), 
                data=chapter
            )
            if pictures:
                return pictures
        except Exception as er:
            logger.exception(f"Error in process_pictures: {er}")
            

        if attempt < 2:
            await asyncio.sleep(6)

    return []


# ============================================
# add_update_queue - parallel picture fetch
# ============================================
async def add_update_queue(
    web_class, user_id, update_manga: list, user_mention: str
):
    if Vars.IS_PRIVATE and user_id == "shared_admin_subs":
        user_id = Vars.ADMINS[0]
    elif user_id == "shared_admin_subs":
        await database.delete_user(user_id)
        return

    user_id = str(user_id)
    if isinstance(web_class, str):
        web_class = get_webs(web_class)

    # Fetch settings + all pictures at same time
    user_settings, *pictures_list = await asyncio.gather(
        database.get_settings(user_id),
        *[process_pictures(web_class, ch) for ch in update_manga],
        return_exceptions=True
    )

    for manga_chapter, pictures in zip(update_manga, pictures_list):
        try:
            if isinstance(pictures, Exception) or not pictures:
                logger.error(f"No pictures: {manga_chapter.get('url')}")
                continue

            manga_url = manga_chapter.get("manga_url")
            chapter_url = manga_chapter.get("url")
            if not manga_url or not chapter_url:
                continue

            updated = await database.save_latest_chapter(
                {
                    "url": manga_url,
                    "title": manga_chapter.get("manga_title", ""),
                    "lastest_chapter": manga_chapter.get("title", ""),
                },
                str(user_id),
                web_class.sf
            )

            message = (
                f"<b><i>Updates: {manga_chapter.get('manga_title', 'N/A')} "
                f"- {manga_chapter.get('title', 'N/A')}</i></b>\n\n"
                f"Url: {chapter_url}\n"
                f"User: {user_mention}"
            )

            if not updated:
                err_txt = (
                    f"<b><i>Fail to Update the lastest chapters"
                )
                await send_message(Vars.LOG_CHANNEL, err_txt + message)
                continue



            # Send status + log at same time
            sts, _ = await asyncio.gather(
                send_message(
                    int(user_id),
                    message + "\n\nStatus: <code>Added At Queue</code>"
                ),
                retry_on_flood(Bot.send_message)(Vars.LOG_CHANNEL, message)
                if Vars.LOG_CHANNEL else asyncio.sleep(0),
                return_exceptions=True
            )

            if not sts:
                return

            num = random.choice(string.ascii_uppercase + string.digits)
            uid_short = user_id[3:] if len(user_id) > 3 else user_id


            task_card = TaskCard(
                data_list=[manga_chapter.copy()],
                webs=web_class,
                sts=sts,
                user_id=int(user_id),
                chat_id=int(user_id),
                priority=1,
                tasks_id=f"U_{uid_short}_{num}",
                update_mode=True,
                settings=user_settings if isinstance(user_settings, dict) else {},
            )

            # Save + queue at same time
            await queue.put(task_card, True)


        except Exception as er:
            logger.exception(f"Error in add_update_queue: {er}")


# ============================================
# update_worker
# ============================================
async def update_worker() -> None:
        try:
            web_class, user_id, update_manga, user_mention = await picture_queue.get()

            logger.info(f"Worker: {len(update_manga)} chapters for {user_id}")
            await add_update_queue(web_class, user_id, update_manga, user_mention)
        except Exception as er:
            logger.exception(f"update_worker error: {er}")


# ============================================
# update_subs command
# ============================================
@Bot.on_message(filters.command("update_subs"))
async def update_subs(client, message):
    user_data = await database.get_users_data(message.from_user.id)

    subs_data = user_data.get("subs", {}) if user_data else {}
    if not subs_data:
        await retry_on_flood(message.reply_text)(
            "<b><i>You have no subscribed manga</i></b>"
        )
        return

    sts = await retry_on_flood(message.reply_text)(
        "<b><i>Checking for updates...\n\n=> This will take a while... </i></b>",
    )

    try:
        total = len(subs_data)
        updated = await process_user(user_data)

        percentage = (updated * 100 / total) if total > 0 else 0
        filled = floor(percentage / 5)

        progress = "{0}{1}".format(
            "⬢" * filled,
            "⬡" * (20 - filled)
        )

        text = (
            f"<b>[{progress}] {percentage:.2f}%\n\n"
            f"=> Total Manga: {total}\n"
            f"=> Manga Updated: {updated}\n"
            f"Dev: @Shanks_pro</b>"
        )
        await igrone_error(sts.edit_text)(text)

    except Exception as er:
        logger.exception(f"update_subs error: {er}")
        await retry_on_flood(sts.edit_text)(f"<b><i>Error: {er}</i></b>")

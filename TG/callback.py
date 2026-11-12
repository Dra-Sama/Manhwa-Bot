# Code By @V_Sbotmaker (on Telegram)
from typing import Optional
from TG.cmds import get_webs, check_get_web
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, CallbackQuery

from .storage import (
   searchs, pagination, subscribes, _storage,
   retry_on_flood, igrone_error, check_fsb, queue,
   split_list, chaptersList, get_episode_number, is_auth_query,
   TTLCache, iter_chapters
)

from bot import Bot, Vars, logger
import random

from Tools.db import database, get_effective_user_id
from Tools.base import Subscribes, TaskCard, MangaCard, FloodWait
import asyncio, inspect
from Tools.ihandler import ihandler

c_p = 40  # chapters per page
_chapter_cache = TTLCache(default_timeout=10 * 60)  # 10 mins


@Bot.on_callback_query(filters.regex("^just_kidding$"))
async def just_kidding_handler(_, query):
    await igrone_error(query.answer)()#"💘  𝗛𝗼𝗻𝘁𝗼 𝗻𝗶 𝗮𝗿𝗶𝗴𝗮𝘁𝗼 𝗴𝗼𝘇𝗮𝗶𝗺𝗮𝘀𝘂....  💘")


@Bot.on_callback_query(filters.regex("^refresh$"))
async def refresh_handler(_, query):
    if not _.FSB or _.FSB == []:
        await retry_on_flood(query.answer)(
            " ✅ Thanks for joining! You can now use the bot. ",
            show_alert=True
        )
        return await retry_on_flood(query.message.delete)()

    channel_button, change_data = await check_fsb(_, query)
    if not channel_button:
        await retry_on_flood(query.answer)(
            " ✅ Thanks for joining! You can now use the bot. ",
            show_alert=True
        )
        return await retry_on_flood(query.message.delete)()

    channel_button = split_list(channel_button)
    channel_button.append([InlineKeyboardButton("ʀᴇғʀᴇsʜ ⟳", callback_data="refresh")])

    try:
        await retry_on_flood(query.edit_message_media)(
            media=InputMediaPhoto(
                random.choice(Vars.PICS),
                caption=Vars.FORCE_SUB_TEXT
            ),
            reply_markup=InlineKeyboardMarkup(channel_button),
        )
    except Exception:
        await retry_on_flood(query.answer)("You're still not in the channel.")

    if change_data:
        for change_ in change_data:
            _.FSB[change_[0]] = (change_[1], change_[2], change_[3])


@Bot.on_callback_query(filters.regex("^close|kclose$"))
async def close_handler(client, query):
    await igrone_error(query.answer)()

    try:
        if client.id != query.message.reply_to_message.chat.id:
            await retry_on_flood(query.message.reply_to_message.delete)()
    except Exception:
        pass
    try:
        await retry_on_flood(query.message.delete)()
    except Exception:
        pass


@Bot.on_callback_query(filters.regex("^premuim$"))
async def premuim_handler(_, query):
    """Premium pricing handler."""
    button = query.message.reply_markup.inline_keyboard
    text = """
<b><i>Premium Price

Pricing Rates
  7 Days - 30 inr / 0.35 USD / NRS 40
  1 Month - 90 inr / 1.05 USD / NRS 140
  3 Months - 260 inr / 2.94 USD / NRS 350
  6 Months - 500 inr / 6.33 USD / NRS 700
  9 Months - 780 inr / 9.14 USD / NRS 1100
  12 Months - 1000 inr / 11.8 USD / NRS 1400

Want To Buy ?!
  Contact or DM - @Shanks_Pro

We Have Limited Seats For Premium Users</i></b>"""
    try:
        del button[-2]
        await retry_on_flood(query.edit_message_media)(
            media=InputMediaPhoto(random.choice(Vars.PICS), caption=text),
            reply_markup=InlineKeyboardMarkup(button)
        )
    except Exception:
        button = [[InlineKeyboardButton(" Close ", callback_data="kclose")]]
        await retry_on_flood(query.edit_message_media)(
            media=InputMediaPhoto(random.choice(Vars.PICS), caption=text),
            reply_markup=InlineKeyboardMarkup(button)
        )


async def get_chapters_cached(manga_card) -> MangaCard:
    cache_key = f"chapters:{hash(manga_card.url)}"

    cached = _chapter_cache.get(cache_key)
    if cached is not None:
        bio_list = cached
    else:
        data = manga_card.load_to_dict()
        bio_list = await asyncio.wait_for(
            manga_card.webs.get_chapters(data),
            timeout=200
        )
        _chapter_cache[cache_key] = bio_list

    manga_card.update_dict(bio_list)

    if hasattr(manga_card.webs, 'iter_chapters'):
        fn = manga_card.webs.iter_chapters
    else:
        fn = iter_chapters

    result = fn(bio_list, page=1)

    manga_card.chapters = (
        await asyncio.wait_for(result, timeout=200)
        if inspect.isawaitable(result)
        else result
    )

    return manga_card


@Bot.on_callback_query(filters.regex("^chs") & is_auth_query())
async def ch_handler(client, query: CallbackQuery):
    """Chapter info handler."""
    try:
        manga_card: MangaCard = searchs[query.data]
        new_callback = str(query.data).replace("chs", "pg", 1)
    except Exception:
        return await query.answer(
            "This is an old button, please redo the search",
            show_alert=True
        )


    if not manga_card.chapters:
        try:
            manga_card = await get_chapters_cached(manga_card)
        except Exception as er:
            logger.exception(er)
            await igrone_error(query.answer)("Site has been Updated")
            return

    if not isinstance(manga_card, MangaCard):
        return await igrone_error(query.answer)("There is Issue at line 163, Tell To dev 😐")

    if not manga_card.webs:
        manga_card.webs = check_get_web(manga_card.url)

    subs_bool = await database.get_subs(
        query.from_user.id, manga_url=manga_card.url,
        web=manga_card.webs.sf
    )

    try:
        last_ep = manga_card.chapters[0]['title'] if manga_card.chapters else ""
    except Exception:
        last_ep = ""

    sdata = Subscribes(
        manga_url=manga_card.url,
        manga_title=manga_card.title,
        webs=manga_card.webs.sf,
        lastest_chapter=last_ep
    )
    sc = f"subs:{hash(manga_card.url)}"
    subscribes[sc] = sdata

    rand_pic = manga_card.poster or random.choice(Vars.PICS)
    lastest_chapter = subs_bool.get("lastest_chapter", None) if isinstance(subs_bool, dict) else None

    caption = manga_card.msg[:1024] if manga_card.msg else f"<b>{manga_card.title}</b>"


    if manga_card.chapters and any(i.get('group_name') for i in manga_card.chapters if isinstance(i, dict)):
        try:
            scans_callback = f"scg:{manga_card.webs.sf}:{hash(manga_card.chapters[-1]['url'])}"
        except Exception:
            scans_callback = f"scg:{manga_card.webs.sf}:{hash(manga_card.url)}"

        _storage[scans_callback] = manga_card

        button = [
            [
                InlineKeyboardButton("▸ ᴄʜᴀᴘᴛᴇʀs ◂", callback_data=new_callback),
                InlineKeyboardButton("▸ ꜱᴄᴀɴʟᴀᴛɪᴏɴ ɢʀᴏᴜᴘ ◂", callback_data=scans_callback),
            ],
            [
                InlineKeyboardButton("✘ ᴜɴsᴜʙsᴄʀɪʙᴇ ✘", callback_data=sc)
                if subs_bool else
                InlineKeyboardButton("✓ sᴜʙsᴄʀɪʙᴇ ✓", callback_data=sc)
            ],
        ]
    else:
        button = [
            [
                InlineKeyboardButton("▸ ᴄʜᴀᴘᴛᴇʀs ◂", callback_data=new_callback),
                InlineKeyboardButton(f"▸ {lastest_chapter} ◂", callback_data="just_kidding")
            ],
            [
                InlineKeyboardButton("✘ ᴜɴsᴜʙsᴄʀɪʙᴇ ✘", callback_data=sc)
                if subs_bool else
                InlineKeyboardButton("✓ sᴜʙsᴄʀɪʙᴇ ✓", callback_data=sc)
            ],
        ]

    try:
        await send_or_edit(
            query=query, caption=caption, button=button,
            rand_pic=rand_pic, web_sf=manga_card.webs.sf
        )
    except Exception as er:
        logger.exception(er)
        await retry_on_flood(query.message.reply_text)(f"<code>{er}</code>")

    await igrone_error(query.answer)()


async def send_or_edit(
    query: CallbackQuery, caption: str, button: list,
    rand_pic: str, web_sf: str
):
    back_close = [
        InlineKeyboardButton("⇦ 𝗕𝗔𝗖𝗞", callback_data=f"plugin_{web_sf}"),
        InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="kclose"),
    ]
    plain_close = [
        InlineKeyboardButton(" (っ◔◡◔)っ ", callback_data=query.data),
        InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="kclose"),
    ]

    edit_markup  = InlineKeyboardMarkup(button + [back_close])
    reply_markup = InlineKeyboardMarkup(button + [plain_close])
    media        = InputMediaPhoto(rand_pic, caption=caption)


    attpt = 0
    while attpt <= 3:
        try:
            return await query.message.reply_photo(
                photo=rand_pic,
                caption=caption,
                reply_markup=reply_markup,
            )
        except FloodWait as e:
            pass
            # this help to know which function have floodwaits and switch other
        except Exception:
            rand_pic = random.choice(Vars.PICS)
            media    = InputMediaPhoto(rand_pic, caption=caption)
            attpt   += 1

    # Fall back to edit_message_media
    try:
        return await retry_on_flood(query.edit_message_media)(
            media=media,
            reply_markup=edit_markup,
        )
    except Exception:
        try:
            return await retry_on_flood(query.message.reply_photo)(
                photo=rand_pic,
                caption=caption,
                reply_markup=reply_markup,
            )
        except Exception:
            return await retry_on_flood(query.message.reply_photo)(
                photo=Vars.PICS[-1],
                caption=caption,
                reply_markup=reply_markup,
            )


def _create_chapters_button_(
    chapters: list, page: int, manga_card: MangaCard,
    mode: bool = False, subs_bool: Optional[dict] = None,
    reply_to_message: Optional[bool] = False
) -> list:
    if not chapters or not manga_card:
        return []

    if manga_card.webs is None:
        manga_card.webs = check_get_web(manga_card.url)

    page = int(page)
    webs_sf = manga_card.webs.sf

    # Pre-compute pagination once
    total_chapters = len(chapters)
    total_pages    = (total_chapters + c_p - 1) // c_p

    def get_page_slice(p: int) -> list:
        if p < 1 or p > total_pages:
            return []
        start = (p - 1) * c_p
        return chapters[start: start + c_p]

    current_chapters = get_page_slice(page)
    if not current_chapters:
        return []

    # Build chapter buttons + batch storage writes in one pass
    button        = []
    storage_batch = {}

    for chapter in current_chapters:
        c = f"pic|{hash(chapter['url'])}"
        storage_batch[c] = (manga_card.webs, chapter)

        chapter_title = (
            f"{chapter['title']} [{chapter['group_name']}]"
            if chapter.get('group_name')
            else chapter['title']
        )
        button.append(InlineKeyboardButton(chapter_title, callback_data=c))

    chaptersList.update(storage_batch)
    button = split_list(button)

    # Pagination row — previous
    pagination_key  = f"pg:{webs_sf}:{hash(chapters[-1]['url'])}:"
    pagination_key += "m:" if mode else "n:"
    pagination[pagination_key] = (
        (manga_card, []) if manga_card.chapters == chapters
        else (manga_card, chapters)
    )

    pre_page_ = []
    for offset in [1, 2, 5]:
        prev = page - offset
        if prev >= 1:
            pre_page_.append(InlineKeyboardButton(
                f"{'<<' if offset == 1 else f'<{offset}x'}",
                callback_data=f"{pagination_key}{prev}"
            ))

    if pre_page_:
        button.append(pre_page_)

    # Pagination row — next
    next_page_ = []
    for offset in [1, 2, 5]:
        nxt = page + offset
        if nxt <= total_pages:
            next_page_.append(InlineKeyboardButton(
                f"{'>>' if offset == 1 else f'{offset}x>'}",
                callback_data=f"{pagination_key}{nxt}"
            ))

    if next_page_:
        button.append(next_page_)

    # Batch remaining storage writes
    all_data      = f"full:{webs_sf}:{hash(chapters[-1]['url'])}{hash(chapters[0]['url'])}"
    callback_data = f"full:{webs_sf}:{len(current_chapters)}:{hash(current_chapters[0]['url'])}"
    _storage.update({
        all_data:      (chapters, manga_card.webs),
        callback_data: (current_chapters, manga_card.webs),
    })

    # Bottom buttons
    if any(i.get('group_name') for i in manga_card.chapters or [] if isinstance(i, dict)):
        if mode:
            c = f"pg:{webs_sf}:{hash(manga_card.chapters[-1]['url'])}:n:"
            pagination[c] = (manga_card, [])
            button.append([InlineKeyboardButton("♚ ᴄʜᴀᴘᴛᴇʀꜱ ♚", callback_data=c)])

        else:
            scans_callback = all_data.replace("full", "scg", 1)
            _storage[scans_callback] = manga_card
            button.append([InlineKeyboardButton("♚ ꜱᴄᴀɴʟᴀᴛɪᴏɴ ɢʀᴏᴜᴘ ♚", callback_data=scans_callback)])

    button.append([
        InlineKeyboardButton(" Single CBZ ", callback_data=all_data.replace('full', 'scbz'))
    ])

    button.append([
        InlineKeyboardButton("⇧ ғᴜʟʟ ᴘᴀɢᴇ ⇧", callback_data=callback_data),
        InlineKeyboardButton("⇧ ᴀʟʟ ᴄʜᴀᴘᴛᴇʀꜱ ⇧", callback_data=all_data),
    ])

    # Subscribe button
    try:
        last_ep = manga_card.chapters[0]['title'] if manga_card.chapters else ""
    except Exception:
        last_ep = ""

    sdata = Subscribes(
        manga_url=manga_card.url,
        manga_title=manga_card.title,
        webs=webs_sf,
        lastest_chapter=last_ep
    )
    sc = f"subs:{hash(manga_card.url)}"
    subscribes[sc] = sdata

    lastest_ep_db = (
        subs_bool.get("lastest_chapter", "(っ◔◡◔)っ")
        if isinstance(subs_bool, dict)
        else "(っ◔◡◔)っ"
    ) or "(っ◔◡◔)っ"

    if webs_sf != "dj":
        button.append([
            InlineKeyboardButton("✘ ᴜɴsᴜʙsᴄʀɪʙᴇ ✘", callback_data=sc)
            if subs_bool else
            InlineKeyboardButton("✓ sᴜʙsᴄʀɪʙᴇ ✓", callback_data=sc)
        ])

    if reply_to_message:
        button.append([
            InlineKeyboardButton("⇦ 𝗕𝗔𝗖𝗞", callback_data=f"plugin_{webs_sf}"),
            InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="kclose")
        ])
    else:
        button.append([
            InlineKeyboardButton(f"▸ {lastest_ep_db} ◂", callback_data="just_kidding"),
            InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="kclose")
        ])

    return button


@Bot.on_callback_query(filters.regex("^pg") & is_auth_query())
async def pg_handler(_, query):
    """Pagination handler."""
    if (check_ := (str(query.data).replace("pg", "chs", 1))) in searchs:
        manga_card = searchs[check_]
        page  = 1
        mode  = False
        chapters = manga_card.chapters

    else:
        call_data = query.data.split(":")

        try:
            page      = call_data[-1]
            mode      = call_data[-2]
            mode      = True if mode == "m" else False
            call_data = str(query.data).removesuffix(f"{page}")
        except Exception:
            call_data = "a"

        if call_data not in pagination:
            await igrone_error(query.answer)(
                "This is an old button, please redo the search",
                show_alert=True
            )
            return

        manga_card, chapters = pagination[call_data]
        if not chapters:
            chapters = manga_card.chapters

    try:
        page = int(page)
    except Exception:
        page = 1


    total_pages = (len(chapters) + c_p - 1) // c_p
    if not chapters or page < 1 or page > total_pages:
        return await query.answer("No chapters found", show_alert=True)

    subs_bool = await database.get_subs(
        str(query.from_user.id), manga_url=manga_card.url,
    )

    button = _create_chapters_button_(
        chapters=chapters, page=page,
        manga_card=manga_card, subs_bool=subs_bool, mode=mode,
        reply_to_message=bool(query.message.reply_to_message)
    )
    if not button:
        return await igrone_error(query.answer)("No chapters found", show_alert=True)

    await igrone_error(query.answer)()
    await retry_on_flood(query.edit_message_reply_markup)(InlineKeyboardMarkup(button))


@Bot.on_callback_query(filters.regex('^scbz') & is_auth_query())
async def single_cbz_handler(_, query):
    cldata = str(query.data).replace('scbz', 'full')
    if cldata not in _storage:
        await retry_on_flood(query.answer)(
            "This is an old button, please redo the search",
            show_alert=True
        )
        return
    try:
        chapters, webs = _storage[cldata]

        user_settings, priority = await asyncio.gather(
            database.get_settings(query.from_user.id),
            database.premium_user(query.from_user.id),
        )

        user_settings['type'] = ['cbz']

        priority = 1 if priority else 0

        chapters_list = list(reversed(list(
            {get_episode_number(c['title']): c for c in chapters}.values()
        )))

        if not chapters_list:
            await igrone_error(query.answer)("No chapters found", show_alert=True)
            return

        args = [(c['url'], c) for c in chapters_list]
        ihandler.order_batch(str(query.from_user.id), webs, args)

        loop = asyncio.get_running_loop()
        loop.create_task(queue.put(TaskCard(
            data_list=chapters_list,
            webs=webs,
            sts=None,
            user_id=query.from_user.id,
            chat_id=query.message.chat.id,
            priority=priority,
            settings=user_settings,
        )))
        await igrone_error(query.answer)(" Added In Queue")
    except Exception as err:
        logger.exception(err)
        await retry_on_flood(query.message.reply_text)(f"`{err}`")
        await igrone_error(query.answer)()


@Bot.on_callback_query(filters.regex("^full") & is_auth_query())
async def full_handler(_, query):
    bot_token = await database.get_bot_token(query.from_user.id)
    if not bot_token:
        await query.answer(
            "You need to configure your own bot to use Download All Chapters. Use /mybot command to set it up.",
            show_alert=True
        )
        return

    if query.data not in _storage:
        await retry_on_flood(query.answer)(
            "This is an old button, please redo the search",
            show_alert=True
        )
        return

    chapters, webs = _storage[query.data]

    try:
        user_settings, priority = await asyncio.gather(
            database.get_settings(query.from_user.id),
            database.premium_user(query.from_user.id),
        )
        priority = 1 if priority else 0

        chapters_list = list(reversed(list(
            {get_episode_number(c['title']): c for c in chapters}.values()
        )))

        if not chapters_list:
            await igrone_error(query.answer)("No chapters found", show_alert=True)
            return

        merge_size = user_settings.get('megre', None)
        if merge_size:
            try:
                merge_size = int(merge_size)
            except (ValueError, TypeError):
                merge_size = 1

        merge_size = merge_size or 1

        all_chunks = list(split_list(chapters_list, merge_size))

        await igrone_error(query.answer)(
            f"Adding {len(all_chunks)} Chapters To Queue...",
            show_alert=True
        )

        # Offload the chunk loop to a background task so the callback query doesn't timeout
        async def queue_all_chapters():
            added_count = 0
            for data_list in all_chunks:
                args = [(c['url'], c) for c in data_list]
                ihandler.order_batch(str(query.from_user.id), webs, args)

                try:
                    await queue.put(TaskCard(
                        data_list=data_list,
                        webs=webs,
                        sts=None,
                        user_id=query.from_user.id,
                        chat_id=query.message.chat.id,
                        priority=priority,
                        settings=user_settings,
                    ))
                    added_count += 1
                    await asyncio.sleep(0.05) # small sleep to prevent event loop blocking
                except Exception as e:
                    logger.error(f"Error adding chapter to queue: {e}")
                    if "Queue full" in str(e):
                        await retry_on_flood(query.message.reply_text)("Queue is full! Some chapters were not added.")
                        break

        # Dispatch task to the active running loop
        loop = asyncio.get_running_loop()
        loop.create_task(queue_all_chapters())

    except Exception as err:
        logger.exception(err)
        await retry_on_flood(query.message.reply_text)(f"`{err}`")
        await igrone_error(query.answer)()


@Bot.on_callback_query(filters.regex("^pic") & is_auth_query())
async def pic_handler(_, query):
    """Single chapter picture handler."""
    if query.data not in chaptersList:
        await igrone_error(query.answer)(
            "This is an old button, please redo the search", show_alert=True
        )
        return

    webs, data = chaptersList[query.data]
    user_id = query.from_user.id

    try:
        pictures = await ihandler.get_cache_pictures(webs, data['url'], data=data)
    except Exception as er:
        logger.exception(er)
        return await igrone_error(query.answer)("No pictures found", show_alert=True)

    if not pictures:
        return await igrone_error(query.answer)("No pictures found", show_alert=True)

    _, sts = await asyncio.gather(
        database.ensure_user(user_id),
        retry_on_flood(query.message.reply_text)("<code>Adding...</code>")
    )

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(ihandler.order(
            user_id=user_id, webs=webs,
            chapter_url=data['url'], data=data
        ))

        priority, uts = await asyncio.gather(
            database.premium_user(user_id),
            database.get_settings(user_id)
        )
        priority = 1 if priority else 0

        task_id = await queue.put(
            TaskCard(
                data_list=[data.copy()],
                webs=webs,
                sts=sts,
                user_id=query.from_user.id,
                chat_id=query.message.chat.id,
                priority=priority,
                settings=uts
            ),
        )
        txt   = f"<i>Manga Name: **{data['manga_title']}** Chapter: - **{data['title']}**</i>"

        button = [[InlineKeyboardButton(" Cancel Your Tasks ", callback_data=f"cql:{task_id}")]]
        await retry_on_flood(sts.edit)(txt, reply_markup=InlineKeyboardMarkup(button))
        await igrone_error(query.answer)(f"Your {task_id} added at queue")

    except Exception as err:
        logger.exception(err)
        await retry_on_flood(sts.edit)(f"`{str(err)}`")
        await igrone_error(query.answer)()


@Bot.on_callback_query(filters.regex("^cql"))
async def cl_handler(client, query):
    """Cancel task handler."""
    task_id = query.data.split(":")[-1]
    if await queue.delete_task(task_id):
        await retry_on_flood(query.message.edit_text)("<i>Your Task Cancelled !</i>")
    else:
        await retry_on_flood(query.answer)(" Task Not Found ", show_alert=True)
        await retry_on_flood(query.message.delete)()


@Bot.on_callback_query(filters.regex("^scg") & is_auth_query())
async def query_group_handler(_, query):
    """Scanlation group handler."""
    if query.data not in _storage:
        await igrone_error(query.answer)(
            "This is an old button, please redo the search", show_alert=True
        )
        return

    manga_card = _storage[query.data]
    if not manga_card.chapters:
        await igrone_error(query.answer)("No chapters found", show_alert=True)
        return

    group_raw = {}
    for chapter in manga_card.chapters:
        key = (chapter.get("group_name") or "Unknown").lower()
        group_raw.setdefault(key, []).append(chapter)

    if not group_raw:
        await igrone_error(query.answer)("No chapters found", show_alert=True)
        return

    sorted_groups = sorted(group_raw.items(), key=lambda x: len(x[1]), reverse=True)

    button = []
    for group_name, grp_chapters in sorted_groups:
        c = f"sfc:{manga_card.webs.sf}:{hash(grp_chapters[0]['url'])}:{hash(grp_chapters[-1]['url'])}"
        _storage[c] = (grp_chapters, manga_card)
        button.append(InlineKeyboardButton(
            f"{group_name} [{len(grp_chapters)}]",
            callback_data=c
        ))

    button = split_list(button)
    button.insert(0, [InlineKeyboardButton(
        " 𝙲𝚑𝚘𝚘𝚜𝚎 𝚂𝚌𝚊𝚗𝚕𝚊𝚝𝚘𝚛 ",
        copy_text="  𝗞𝗼𝗻𝗻𝗶𝗰𝗵𝗶𝘄𝗮 𝗦𝗲𝗻𝗽𝗮𝗶 , 𝗴𝗼-𝗿𝗶𝘆ō 𝗮𝗿𝗶𝗴𝗮𝘁ō 𝗴𝗼𝘇𝗮𝗶𝗺𝗮𝘀𝘂..  "
    )])

    subs_bool = await database.get_subs(
        str(query.from_user.id), manga_card.url, manga_card.webs.sf
    )

    c = f"pg:{manga_card.webs.sf}:{hash(manga_card.chapters[-1]['url'])}:n:"
    pagination[c] = (manga_card, [])
    button.append([InlineKeyboardButton("♚ ᴄʜᴀᴘᴛᴇʀꜱ ♚", callback_data=c)])

    sdata = Subscribes(
        manga_url=manga_card.url,
        manga_title=manga_card.title,
        webs=manga_card.webs.sf,
        lastest_chapter=manga_card.chapters[0]['title'] if manga_card.chapters else ""
    )
    sc = f"subs:{hash(manga_card.url)}"
    subscribes[sc] = sdata

    if manga_card.webs.sf != "dj":
        button.append([
            InlineKeyboardButton("✘ ᴜɴsᴜʙsᴄʀɪʙᴇ ✘", callback_data=sc)
            if subs_bool else
            InlineKeyboardButton("✓ sᴜʙsᴄʀɪʙᴇ ✓", callback_data=sc)
        ])

    button.append([InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="kclose")])
    await retry_on_flood(query.edit_message_reply_markup)(InlineKeyboardMarkup(button))


@Bot.on_callback_query(filters.regex("^sfc") & is_auth_query())
async def scg_group_handler(_, query):
    """Sub-group chapter list handler."""
    if query.data not in _storage:
        await igrone_error(query.answer)(
            "This is an old button, please redo the search", show_alert=True
        )
        return

    chapters, manga_card = _storage[query.data]
    subs_bool = await database.get_subs(
        str(query.from_user.id), manga_card.url, manga_card.webs.sf
    )

    button = _create_chapters_button_(
        chapters=chapters, page=1, subs_bool=subs_bool,
        manga_card=manga_card, mode=True
    )
    if not button:
        return await igrone_error(query.answer)("No chapters found", show_alert=True)

    await igrone_error(query.answer)()
    await retry_on_flood(query.edit_message_reply_markup)(InlineKeyboardMarkup(button))


@Bot.on_callback_query(filters.regex("^src_noop$"))
async def src_noop_handler(_, query):
    await igrone_error(query.answer)()


@Bot.on_callback_query(filters.regex("^sources_panel:(\\d+)$"))
async def sources_panel_handler(_, query):
    page = int(query.matches[0].group(1))
    from .settings import get_sources_panel  # noqa: PLC0415
    text, reply_markup = await get_sources_panel(query.from_user.id, page=page)
    await igrone_error(query.answer)()
    try:
        await retry_on_flood(query.edit_message_media)(
            media=InputMediaPhoto(random.choice(Vars.PICS), caption=text),
            reply_markup=reply_markup,
        )
    except Exception:
        await retry_on_flood(query.edit_message_reply_markup)(reply_markup)


@Bot.on_callback_query(filters.regex("^src_toggle:([a-zA-Z0-9_]+):(\\d+)$"))
async def src_toggle_handler(_, query):
    sf = query.matches[0].group(1)
    page = int(query.matches[0].group(2))

    is_now_enabled = await database.toggle_user_source(query.from_user.id, sf)
    from .settings import get_sources_panel  # noqa: PLC0415
    text, reply_markup = await get_sources_panel(query.from_user.id, page=page)

    status_msg = "Source Enabled ✅" if is_now_enabled else "Source Disabled ❌"
    await igrone_error(query.answer)(status_msg)

    try:
        await retry_on_flood(query.edit_message_reply_markup)(reply_markup)
    except Exception:
        pass


@Bot.on_callback_query(filters.regex("^src_re_enable:([a-zA-Z0-9_]+):(\\d+)$"))
async def src_re_enable_handler(_, query):
    sf = query.matches[0].group(1)
    page = int(query.matches[0].group(2))
    user_id = query.from_user.id

    is_admin = False
    try:
        if int(user_id) in Vars.ADMINS:
            is_admin = True
    except (ValueError, TypeError):
        pass
    if hasattr(Vars, "OWNER") and str(Vars.OWNER) == str(user_id):
        is_admin = True

    if not is_admin:
        return await igrone_error(query.answer)(
            "⚠️ This source was automatically disabled due to repeated failures. Contact Bot Admins to re-enable it.",
            show_alert=True
        )

    await database.re_enable_source(sf)
    await igrone_error(query.answer)("✅ Source re-enabled globally! Retry counter reset to 0.", show_alert=True)

    from .settings import get_sources_panel  # noqa: PLC0415
    text, reply_markup = await get_sources_panel(user_id, page=page)
    try:
        await retry_on_flood(query.edit_message_reply_markup)(reply_markup)
    except Exception:
        pass

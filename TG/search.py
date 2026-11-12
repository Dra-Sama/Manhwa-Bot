# Code By @V_Sbotmaker (on Telegram)
from Tools.base import MangaCard, TTLCache
from bot import  Bot, Vars, logger
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
import random

from Tools.db import database

from .storage import (
    get_webs, igrone_error, plugins_list,
    retry_on_flood, searchs, is_auth_query,
    web_data, check_get_web, Listeing_cache,
    log_fu, search_storage_cache, function_cache,
    split_list
)

from .subscribe import isubs_callback
from Tools.my_token import check_token_
import asyncio

from functools import wraps
import hashlib
import re


WEBSITE_SUFFIX_PATTERN = re.compile(r'Webs|Source|Website')


def lu_cache(func):
    """Direct decorator without parameters"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Get or create function-specific cache
        func_cache = function_cache.setdefault(func.__name__, {})

        # Create key
        key_data = f"{args}:{tuple(sorted(kwargs.items()))}"
        key = hashlib.md5(key_data.encode()).hexdigest()

        try:
            return func_cache[key]
        except KeyError:
            result = func(*args, **kwargs)
            func_cache[key] = result
            return result

    wrapper.cache_clear = lambda: function_cache.pop(func.__name__, None)  # type: ignore

    return wrapper

@lu_cache
def clean_website_name(name: str) -> str:
    return WEBSITE_SUFFIX_PATTERN.sub('', name)


@Bot.on_message(filters.command("search"))
@check_token_
async def search_group(client, message):
  if str(message.from_user.id) in Listeing_cache:
      return message.continue_propagation()

  if str(message.from_user.id) in client.listerner:
      return message.continue_propagation()

  if Vars.IS_PRIVATE and message.chat.id not in Vars.ADMINS:
      return await retry_on_flood(message.reply)("<code>You cannot use me baby </code>")

  await database.ensure_user(message.from_user.id)

  try:
    message.text.split(" ")[1]
  except Exception:
    return await retry_on_flood(message.reply)("<code>Format:- /search Manga </code>")

  photo = random.choice(Vars.PICS)
  await retry_on_flood(message.reply_photo)(
      photo, caption="<i>Select search Webs ...</i>",
      reply_markup=await plugins_list(user_id=message.from_user.id),
  )



@Bot.on_message(filters.text & filters.private & ~filters.regex(r"/"))
#@check_token_
async def search(client, message):
    if message.from_user.id in client.listerner:
        return message.continue_propagation()

    if str(message.from_user.id) in Listeing_cache:
        return message.continue_propagation()

    if Vars.IS_PRIVATE and message.chat.id not in Vars.ADMINS:
      return await retry_on_flood(message.reply)("<code>You cannot use me baby </code>")

    await database.ensure_user(message.from_user.id)
    photo = random.choice(Vars.PICS)

    await retry_on_flood(message.reply_photo)(
        photo, caption="<i>Select search Webs ...</i>",
        reply_markup=await plugins_list(user_id=message.from_user.id)
    )


@Bot.on_callback_query(filters.regex("^bk|back_page") & is_auth_query())
async def bk_handler(client, query):
  """This Is Back Handler Of Callback Data"""
  photo = random.choice(Vars.PICS)
  try:
    page = int(query.data.split(":")[-1])
  except Exception:
    page = 1

  await database.ensure_user(query.from_user.id)
  await retry_on_flood(query.message.edit_media)(
      media=InputMediaPhoto(photo, caption="<i>Select The Webs ....</i>"),
      reply_markup=await plugins_list(page=page, user_id=query.from_user.id),
  )
  await igrone_error(query.answer)()



from Webs.source_manager import execute_source_with_retry

@log_fu
async def search_all(search: str, sts, max_concurrent: int = 10):
    """Ultra-low RAM + fast concurrent search with batched progress"""
    semaphore = asyncio.Semaphore(max_concurrent)
    total_websites = len(web_data)

    user_id = None
    try:
        if hasattr(sts, "from_user") and sts.from_user:
            user_id = str(sts.from_user.id)
        elif hasattr(sts, "chat") and sts.chat:
            user_id = str(sts.chat.id)
    except Exception:
        pass

    async def search_one(name: str, web):
        async with semaphore:
            sf = getattr(web, "sf", "")
            url = getattr(web, "url", "")
            clean_name = clean_website_name(str(name))
            try:
                res = await execute_source_with_retry(
                    sf,
                    clean_name,
                    url,
                    web.search,
                    search,
                    user_id=user_id,
                )
                return name, res or []
            except Exception:
                return name, []

    # Create tasks
    tasks = {asyncio.create_task(search_one(name, web)): name
             for name, web in web_data.items()}

    results = []
    found_websites = []
    not_found_websites = []
    processed = 0

    # Process tasks as they complete
    for completed_task in asyncio.as_completed(tasks):
        name, res = await completed_task

        name = clean_website_name(str(name))

        if isinstance(res, list):          # normal result
            if res:
                found_websites.append(name)
                results.extend(res)
            else:
                not_found_websites.append(name)
        else:                              # exception
            not_found_websites.append(name)

        processed += 1

        # Update progress every 2 completed tasks
        if processed % 3 == 0:
            await igrone_error(sts.edit_message_caption)(
                f"<i>Searching: <b>{search}</b> | "
                f"Progress: <b>{processed}/{total_websites}</b></i>"
            )

    MAX_RESULTS = 300
    if len(results) > MAX_RESULTS:
        results = results[:MAX_RESULTS]

    found_text = ", ".join(found_websites) if found_websites else None
    not_found_text = ", ".join(not_found_websites) if not_found_websites else None

    return results, found_text, not_found_text


@log_fu
async def error_pop(
    query, website_name: str,
    search_text: str, website_index_pos: int,
):
    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("𝘊𝘰𝘶𝘭𝘥𝘯'𝘵 𝘧𝘪𝘯𝘥 𝘢𝘯𝘺 𝘮𝘢𝘯𝘨𝘢.", callback_data="just_kidding")
        ],
        [
            InlineKeyboardButton(
                "⇇ Prev Webs ",
                callback_data=f"plugin_/{website_index_pos-1}"
            ),
            InlineKeyboardButton(
                " Next Webs ⇉",
                callback_data=f"plugin_/{website_index_pos+1}"
            )
        ],
        [
            InlineKeyboardButton("✯ Retry ✯", callback_data=query.data)
        ],
        [
            InlineKeyboardButton("⇦ BACK", callback_data="back_page"),
            InlineKeyboardButton("▏CLOSE▕", callback_data="close"),
        ]
    ])
    caption = f"<blockquote><i>No results found for: <b>{search_text}</b> on {website_name}</i></blockquote>"

    photo = random.choice(Vars.PICS)

    await retry_on_flood(query.edit_message_media)(
          InputMediaPhoto(photo, caption=caption),
          reply_markup=reply_markup
    )
    return

@log_fu
async def build_buttons(
    results: list, all_results: list, page: int, data: str,
    websites: str, website_index_pos: int, cb_data: str
) -> list:
    buttons = []

    paginate_results = split_list
    args = (all_results, 15)

    for result in results:
        if not isinstance(result, MangaCard):
            try:
                result = MangaCard.from_dict(result)
            except Exception:
                return []


        result_id = result.data.get('id') or hash(result.url)
        callback_data = f"chs|{data}{result_id}"

        if websites == "all":
          result_website = check_get_web(result.url)
          if not result_website:
              continue

          if result_website:
              result.webs = result_website
              searchs[callback_data] = result
              site_name = clean_website_name(str(type(result_website).__name__))
              button_text = f"{result.title} [{site_name}]"
          else:
              continue
        else:
          result.webs = websites
          searchs[callback_data] = result
          button_text = result.title

        buttons.append([InlineKeyboardButton(button_text, callback_data=callback_data)])


    nav_buttons = []


    if paginate_results(*args, page - 1) and page != 1:
        nav_buttons.append(InlineKeyboardButton("<< ", callback_data=f"plugin_{page-1}_{data}"))

    if paginate_results(*args, page - 2) and page != 1:
        nav_buttons.append(InlineKeyboardButton("<< 2x", callback_data=f"plugin_{page-2}_{data}"))

    if paginate_results(*args, page + 2):
        nav_buttons.append(InlineKeyboardButton("2x >>", callback_data=f"plugin_{page+2}_{data}"))

    if paginate_results(*args, page + 1):
        nav_buttons.append(InlineKeyboardButton(" >>", callback_data=f"plugin_{page+1}_{data}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    extra_bttn = [
        [
            InlineKeyboardButton(
                "⇇ Previous Websites",
                callback_data=f"plugin_/{website_index_pos-1}"
            ),
            InlineKeyboardButton(
                "Next Websites ⇉",
                callback_data=f"plugin_/{website_index_pos+1}"
            )
        ],
        [
            InlineKeyboardButton("✯ Retry ✯", callback_data=cb_data)
        ],
        [
            InlineKeyboardButton("⇦ BACK", callback_data="back_page"),
            InlineKeyboardButton("▏CLOSE▕", callback_data="close"),
        ]
    ]
    buttons.extend(extra_bttn)


    return buttons

@log_fu
async def get_web_index(data_idx, index: bool = False):
    """
    data_idx can be int or str
    if index is True:
      return int index of web_data
    else:
      return str index of web_data
    """
    try:
        data_idx = int(data_idx)
    except Exception:
        data_idx = str(data_idx)


    for i, web in enumerate(web_data.values()):
        web_sf: str = getattr(web, 'sf', 'all')

        if isinstance(data_idx, int) and i == data_idx:
            return i if index else web_sf

        if web_sf == data_idx:
            return i if index else web_sf

        if web_sf.lower() == str(data_idx).lower():
            return i if index else web_sf

    return 0 if index else "all"




@log_fu
async def get_data(callback_type: str, data_parts: list) -> str:
    if "/" in callback_type:
        try:
            data = int(callback_type.split("/")[-1])

            data = await get_web_index(data, index=False)
        except Exception:
            data = await get_web_index(-1)
    else:
        data = data_parts[-1]

    return data


@Bot.on_callback_query(filters.regex("^plugin_") & is_auth_query())
async def cb_handler(client, query):
    """Search Handler Of Callback Data"""
    await database.ensure_user(query.from_user.id)

    callback_type = str(query.data)
    data_parts = str(callback_type).split('_')

    try:
        page = int(data_parts[-2]) #if len(data_parts) > 2 else 1
    except Exception:
        page = 1

    data = await get_data(callback_type, data_parts)
    websites = get_webs(data) or "all"

    if not websites:
        websites = "all"


    website_id = (
        websites if isinstance(websites, str)
        else getattr(websites, 'sf', str(websites))
    )

    reply_msg = query.message.reply_to_message
    search_text = reply_msg.text if hasattr(reply_msg, 'text') else None

    website_name = (
        "All" if websites == "all"
        else clean_website_name(type(websites).__name__)
    )

    (website_index_pos, _) = await asyncio.gather(
        get_web_index(website_id, True),
        database.ensure_user(query.from_user.id),
        return_exceptions=True,
    )
    if isinstance(website_index_pos, Exception):
        website_index_pos = 0


    if search_text is None or search_text == "None":
        await error_pop(
            query, website_name, str(search_text),
            website_index_pos
        )
        return

    if any(cmd in search_text.lower() for cmd in ["/subs", "/subscribes", "/queue"]):
          try:
              return await isubs_callback(client, query)
          except Exception as err:
              logger.exception(f"Error in isubs_callback: {err}")
              await igrone_error(query.answer)("An error occurred", show_alert=True)
              await retry_on_flood(query.message.delete)()
              return


    search_query = (
        search_text.split(" ", 1)[-1].strip()
        if search_text.startswith("/search")
        else search_text.strip()
    ).lower()

    website_cache = search_storage_cache.setdefault(website_id, {})
    cached = website_cache.get(search_query, None)

    await igrone_error(query.edit_message_caption)(
          f"<i>Searching: <b>{search_query}</b>  </i>"
    )
    results = None
    all_results = None
    found_sites = None
    not_found_sites = None

    if cached:
        all_results, found_sites, not_found_sites = cached

    elif websites == "all":
        all_results, found_sites, not_found_sites = await search_all(search_query, query)
        website_cache[search_query] = (all_results, found_sites, not_found_sites)

    else:
        found_sites = not_found_sites = None
        try:
            sf = getattr(websites, "sf", str(website_id))
            url = getattr(websites, "url", "")
            all_results = await execute_source_with_retry(
                sf,
                website_name,
                url,
                websites.search,
                search_query,
                user_id=query.from_user.id,
            ) or []
            website_cache[search_query] = (all_results, found_sites, not_found_sites)
        except Exception as e:
            logger.error(f"Error searching {website_id}: {e}")
            all_results = []

    results = split_list(all_results, 15, page=page)
    if not results or not all_results:
        await error_pop(
          query=query, website_name=website_name,
          search_text=search_query, website_index_pos=website_index_pos
        )
        return


    await igrone_error(query.edit_message_caption)(
          f"<i>Extracting : <b>{search_query}</b> </i>"
    )


    buttons = await build_buttons(
        results, all_results, page, data, websites,
        website_index_pos, query.data
    )
    if not buttons:
        await error_pop(
          query=query, website_name=website_name,
          search_text=search_query, website_index_pos=website_index_pos
        )
        return


    caption_parts = [
        f"<blockquote><i>Search results for: <b>{search_query}</b> "
        f"from <b>{website_name}</b></i></blockquote>"
    ]
    if websites == "all":
        if found_sites:
            caption_parts.append(
                f"\n<blockquote expandable><b>Found Sites:</b> <i>{found_sites}</i></blockquote>"
            )
        if not_found_sites:
            caption_parts.append(
                f"\n<blockquote expandable><b>Sites with no results:</b> <i>{not_found_sites}</i></blockquote>"
            )

    caption = "".join(caption_parts)[:1024]
    photo = random.choice(Vars.PICS)

    try:
        await retry_on_flood(query.edit_message_media)(
          InputMediaPhoto(photo, caption=caption),
          reply_markup=InlineKeyboardMarkup(buttons)
        )
    except TypeError:
        await error_pop(
          query=query, website_name=website_name,
          search_text=search_query, website_index_pos=website_index_pos
        )

    except Exception as e:
        logger.error(f"Error updating message: {e}")
        try:
          await retry_on_flood(query.edit_message_caption)(
              caption=caption,
              reply_markup=InlineKeyboardMarkup(buttons),
          )
        except Exception:
            await error_pop(
              query=query, website_name=website_name,
              search_text=search_query, website_index_pos=website_index_pos
            )

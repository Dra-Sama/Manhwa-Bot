# Code By @V_Sbotmaker (on Telegram)
from typing import Optional
import asyncio
from bot import Bot, Vars, logger
from Tools.db import database, get_episode_number, get_effective_user_id
from TG.storage import igrone_error, subscribes, filters, web_data
import random
from TG.storage import retry_on_flood, check_get_web, is_auth_query, searchs
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from Tools.base import MangaCard, Subscribes
import time
from math import floor
from pyrogram.enums import ButtonStyle



IMPORT_STATE = {}

UPDATE_LS_CONCURRENCY = 5

PAGE_SIZE = 10


@Bot.on_message(filters.command("del_sub") & filters.private)
async def del_sub_cmd(client, message):
  if message.from_user.id not in Vars.ADMINS:
    return message.continue_propagation()

  try:
    user_id = int(str(message.text).split(" ", 1)[-1])
    check_ = await database.delete_user(user_id)
    if check_ is True:
      await retry_on_flood(message.reply_text)("All Subs Deleted")
    else:
      await retry_on_flood(message.reply_text)("Error at Deleting Subs")
      
  except ValueError:
    await retry_on_flood(message.reply_text)("Invalid User ID")
    
  except IndexError:
    await retry_on_flood(message.reply_text)("Please provide a user ID")
  except Exception as er:
    await retry_on_flood(message.reply_text)(f"Error: {er}")


@Bot.on_callback_query(filters.regex("^subs") & is_auth_query())
async def subs_handler(client, query):
  """This Is Subscribe Handler Of Callback Data"""
  user_id = get_effective_user_id(query.from_user.id)
  await database.ensure_user(user_id)

  if query.data not in subscribes:
    await retry_on_flood(query.answer)("This is an old button, please redo the search")
    return

  data_class_ = subscribes[query.data]

  reply_markup = query.message.reply_markup
  button = reply_markup.inline_keyboard
  button_position = -2  # -3 if len(button) >= 3 else -2

  if await database.get_subs(user_id, data_class_.manga_url, data_class_.webs):
    check = await database.delete_sub(user_id, data_class_.manga_url, data_class_.webs)
    if check is not True:
      await retry_on_flood(query.answer)("Error at Removing Subscribe")
      return

    button[button_position] = [
      InlineKeyboardButton(
        "✓ sᴜʙsᴄʀɪʙᴇ ✓", 
        callback_data=query.data,
        style=ButtonStyle.SUCCESS
      )
    ]
    await igrone_error(query.answer)("✅ Comic Unsubscribed!")
  else:
    check = await database.add_sub(user_id, data_class_, data_class_.webs)
    if check is not True:
      await retry_on_flood(query.answer)("Error at Adding Subscribe")
      return

    button[button_position] = [
      InlineKeyboardButton(
        "✘ ᴜɴsᴜʙsᴄʀɪʙᴇ ✘", 
        callback_data=query.data,
        style=ButtonStyle.DANGER
      )]
  
    await igrone_error(query.answer)("🔔 Comic Subscribed!")

  try:
    await retry_on_flood(query.edit_message_reply_markup)(InlineKeyboardMarkup(button))
  except Exception:
    rand_pic = random.choice(Vars.PICS)
    try:
      await retry_on_flood(query.edit_message_media)(
        InputMediaPhoto(rand_pic, caption=query.message.caption),
        reply_markup=InlineKeyboardMarkup(button)
      )
    except Exception as er:
      logger.error(f" Near 48 at subscribe.py {er}")


def _filter_manga_dicts(all_manga_subs: list) -> list:
  if not all_manga_subs:
    return []
  
  return [i for i in all_manga_subs if isinstance(i, dict)]


def iterate_subs(filtered_subs: list, page: int = 1) -> Optional[list]:
  if not filtered_subs:
    return None
    
  start = (page - 1) * PAGE_SIZE
  end = page * PAGE_SIZE
  result = filtered_subs[start:end]
  return result or None


async def isubs_handle(process, page, user_id) -> tuple[list, int]:
  """This Is Subscribe Handler Of Callback Data"""
  user_id = get_effective_user_id(user_id)
  await database.ensure_user(user_id)
  page = int(page)

  raw_subs = await database.get_subs(user_id)

  if not isinstance(raw_subs, list):
    await retry_on_flood(process)(" ` You Have No Subscribe Any Manga `")
    return [], 0

  
  all_manga_subs = _filter_manga_dicts(raw_subs)
  total = len(all_manga_subs)

  if not total:
    await retry_on_flood(process)(" ` You Have No Subscribe Any Manga `")
    return [], 0

  button = []
  start = (page - 1) * PAGE_SIZE
  manga_subs = all_manga_subs[start:start + PAGE_SIZE]

  if not manga_subs:
    return button, total

  logger.debug(f"{len(manga_subs) = }")
  for local_i, data in enumerate(manga_subs):
    manga_url = data.get('url') or data.get('manga_url')
    manga_title = data.get('title') or data.get('manga_title')

    if not manga_url or not manga_title:
      continue

    idx = start + local_i

    web = check_get_web(manga_url)
    if not web:
      button.append([
        InlineKeyboardButton(f"{idx}. {manga_title} [Unknown Site]", callback_data="just_kidding"),
        InlineKeyboardButton("No Scraper", callback_data="just_kidding")
      ])
      continue

    webs_name = type(web).__name__.replace("Webs", "")

    manga_card = MangaCard.from_dict(data)  # Convert to MangaCard Class Object
    if not manga_card:
      continue

    manga_card.url = manga_url  # Ensure correct URL is set
    manga_card.title = manga_title
    manga_card.webs = web
    manga_card.chapters = []

    c = f"chs|{web.sf}{hash(manga_url)}"
    searchs[c] = manga_card

    lastest_ep = get_episode_number(data.get('lastest_chapter', 'None'))
    if lastest_ep is None:
      lastest_ep = data.get('lastest_chapter', 'None')

    button.append([
      InlineKeyboardButton(f"{idx}. {manga_title} [{webs_name}]", callback_data=c),
    ])


  arrow = []
  if page > 1 and 0 <= start - PAGE_SIZE < total:
      arrow.append(InlineKeyboardButton("<<", callback_data=f"isubs:{page-1}"))
    
  if page > 2 and 0 <= start - 2*PAGE_SIZE < total:
      arrow.append(InlineKeyboardButton("<2x", callback_data=f"isubs:{page-2}"))
    
  if 0 <= start + PAGE_SIZE < total:
      arrow.append(InlineKeyboardButton(">>", callback_data=f"isubs:{page+1}"))
    
  if 0 <= start + 2*PAGE_SIZE < total:
      arrow.append(InlineKeyboardButton("2x>", callback_data=f"isubs:{page+2}"))
    
  button.append(arrow)
  button.append([
    InlineKeyboardButton("✵ Clean All Subs ✵", callback_data="pqi_clean_all_subs"),
    InlineKeyboardButton("✵ Refresh ✵", callback_data=f"isubs:{page}")
  ])

  button.append([
    InlineKeyboardButton(" 𝘌𝘹𝘱𝘰𝘳𝘵 ", callback_data="sub_export"),
    InlineKeyboardButton(" 𝘐𝘮𝘱𝘰𝘳𝘵 ", callback_data="sub_json_import")
  ])

  button.append([
      InlineKeyboardButton("◊ ǫᴜᴇᴜᴇ ◊", callback_data="refresh_queue"),
      InlineKeyboardButton("▏CLOSE▕", callback_data="kclose")  
  ])

  return button, total


# ===============================
# Change Lastest Chapter
# ===============================

@Bot.on_message(filters.command(["update_ls"]))
async def update_ls(client, message):
  if Vars.IS_PRIVATE and message.chat.id not in Vars.ADMINS:
    return

  user_id = get_effective_user_id(message.from_user.id)

  subs: list = await database.get_subs(user_id)
  if not subs:
    return await retry_on_flood(message.reply_text)("You Have No Subscribe Any Manga")

  sts = await retry_on_flood(message.reply_text)("<code>Processing...</code>")

  updated, error, db_issue, already_updated = 0, 0, 0, 0
  total = len(subs)
  checked = 0

  async def progress():
    try:
      percentage = checked * 100 / total
    except ZeroDivisionError:
      percentage = 0

    bar = "{0}{1}".format(
        "".join(["⬢" for _ in range(floor(percentage / 5))]),
        "".join(["⬡" for _ in range(20 - floor(percentage / 5))]),
    )

    text = f"""
<b>[{bar}] {percentage:.2f}%

=> Checked: {checked}/{total}
=> Updated: {updated}/{total}
=> Error: {error}

=> DB Issue: {db_issue}
=> already updated : {already_updated} </b>"""
    await igrone_error(sts.edit_text)(text)

  
  semaphore = asyncio.Semaphore(UPDATE_LS_CONCURRENCY)
  lock = asyncio.Lock()

  async def process_one(data: dict):
    nonlocal updated, error, db_issue, already_updated, checked

    manga_url = data.get('url') or data.get('manga_url')
    manga_title = data.get('title') or data.get('manga_title', 'Unknown')
    web = check_get_web(manga_url)

    async with semaphore:
      try:
        if not web:
          logger.warning(f"No scraper found for: {manga_title} ({manga_url})")
          async with lock:
            error += 1
            checked += 1
          return

        manga_card: dict = await web.get_chapters(data)
        chapterlist: list = web.iter_chapters(manga_card, page=1)

        if not chapterlist:
          logger.warning(f"Empty chapter list for: {manga_title} ({manga_url})")
          async with lock:
            error += 1
            checked += 1
          return

        lastest_title = None
        lastest_num = None

        for i in range(min(5, len(chapterlist))):
          temp_title = chapterlist[i].get("title", "")
          temp_num = get_episode_number(temp_title)
          if temp_num:
            lastest_title = temp_title
            lastest_num = temp_num
            break

        if not lastest_num:
          logger.warning(f"Could not extract chapter number for: {manga_title} ({manga_url})")
          async with lock:
            error += 1
            checked += 1
          return

        web_num = get_episode_number(data.get("lastest_chapter", "None"))
        if web_num and web_num == lastest_num:
          async with lock:
            already_updated += 1
            checked += 1
          return

        ok = await database.change_ls(message.from_user.id, lastest_title, manga_url=manga_url)
        async with lock:
          if ok:
            logger.info(f"Updated: {manga_title} -> {lastest_title}")
            updated += 1
          else:
            logger.error(f"DB Issue updating: {manga_title}")
            error += 1
            db_issue += 1
          checked += 1

      except Exception as e:
        logger.error(f"Error processing {manga_title}: {e}")
        async with lock:
          error += 1
          checked += 1

  try:
    tasks = [asyncio.create_task(process_one(data)) for data in subs]

    while not all(t.done() for t in tasks):
      await asyncio.sleep(1.5)
      await progress()

    await asyncio.gather(*tasks)
    await progress()

    await retry_on_flood(sts.edit_text)(
      f"""<b> Completed

=> Updated: {updated}/{total}
=> Error: {error}
=> DB Issue: {db_issue}
=> already updated : {already_updated} </b>""")
  except Exception as er:
    await retry_on_flood(sts.edit_text)(f"Error: {er}")
    logger.exception(er)


@Bot.on_message(filters.command(["cls"]))
async def cls_cmds(_, message):
  if Vars.IS_PRIVATE and message.chat.id not in Vars.ADMINS:
    return

  if len(message.command) < 3:
    await retry_on_flood(message.reply_text)("<b>Usage: /cls {index_num} {chapter_num}</b>")
    return

  sts = await retry_on_flood(message.reply_text)("<code>Processing...</code>")
  try:
    _, index_num, chapter_num = message.command
    index_num = int(index_num)
    chapter_num = int(chapter_num)

    if await database.change_ls(message.from_user.id, chapter_num, index_num=index_num):
      await retry_on_flood(sts.edit)("Lastest Chapter Changed")
      await asyncio.sleep(10)
      await retry_on_flood(sts.delete)()
    else:
      await retry_on_flood(sts.edit)("Error at Changing Lastest Chapter")
  except Exception as er:
    await retry_on_flood(sts.edit)(f"Error: {er}")


@Bot.on_message(filters.command(["subs", "subscribes"]))
async def isubs_cmds(_, message):
  """This Is Subscribe Handler Of Callback Data"""
  if Vars.IS_PRIVATE and message.from_user.id not in Vars.ADMINS:
    return

  sts = await retry_on_flood(message.reply_text)("<code>Processing...</code>")
  user_id = get_effective_user_id(message.from_user.id)

  await database.ensure_user(user_id)

  button, total = await isubs_handle(
    process=sts.edit_text,
    page=1,
    user_id=user_id
  )
  if not total:
    return await igrone_error(sts.edit_text)(" ` You Have No Subscribe Any Manga `")

  caption = f"<b>Your Subscriptions (Total: {total})</b>\n<i>Page 1</i>"
  try:
    await retry_on_flood(sts.edit_media)(
      InputMediaPhoto(random.choice(Vars.PICS), caption=caption),
      reply_markup=InlineKeyboardMarkup(button) if button else None
    )
  except Exception:
    await retry_on_flood(message.reply_photo)(
      photo=random.choice(Vars.PICS),
      caption=caption,
      reply_markup=InlineKeyboardMarkup(button) if button else None,
    )


@Bot.on_callback_query(filters.regex("^isubs") & is_auth_query())
async def isubs_callback(client, query):
  """This Is Subscribe Handler Of Callback Data"""
  try:
    page = int(query.data.split(":")[1])
  except Exception:
    page = 1

  user_id = get_effective_user_id(query.from_user.id)
  await database.ensure_user(user_id)
  button, total = await isubs_handle(
    process=query.answer,
    page=page,
    user_id=user_id
  )
  if not total:
     return await igrone_error(query.answer)("You Have No Subscribe Any Manga")

  await igrone_error(query.answer)()
  caption = f"<b>Your Subscriptions (Total: {total})</b>\n<i>Page {page}</i>"
  try:
    await retry_on_flood(query.edit_message_media)(
      InputMediaPhoto(random.choice(Vars.PICS), caption=caption),
      reply_markup=InlineKeyboardMarkup(button)
    )
  except Exception:
    await igrone_error(query.edit_message_reply_markup)(InlineKeyboardMarkup(button))


@Bot.on_callback_query(filters.regex("^pqi_clean_all_subs$") & is_auth_query())
async def _clean_all_subs_handler(client, query):
  """This Is Clean All Subs Handler Of Callback Data"""
  user_id = get_effective_user_id(query.from_user.id)

  if not await database.get_subs(user_id):
    await query.answer("You Have No Subscribe Any Manga", show_alert=True)
    return

  await database.delete_sub(user_id)
  await query.answer("All Subs Deleted", show_alert=True)
  await igrone_error(query.message.reply_to_message.delete)()
  try:
    await retry_on_flood(query.message.delete)()
  except Exception:
    pass


@Bot.on_callback_query(filters.regex("^sub_export$") & is_auth_query())
async def sub_export_handler(client, query):
  user_id = get_effective_user_id(query.from_user.id)
  await database.ensure_user(user_id)

  subs = await database.get_subs(user_id)

  if not subs:
    return await query.answer("You have no subscriptions to export.", show_alert=True)

  import json
  from io import BytesIO

  data = {"subs": subs}
  json_data = json.dumps(data, indent=2)
  bio = BytesIO(json_data.encode('utf-8'))
  bio.name = f"subscriptions_{user_id}.json"

  await igrone_error(query.answer)("Sending JSON file...")

  await retry_on_flood(client.send_document)(
    chat_id=query.message.chat.id,
    document=bio,
    caption="<b>Here is your Subscriptions JSON data.</b>",
    reply_to_message_id=query.message.reply_to_message.id if query.message.reply_to_message else None
  )


@Bot.on_callback_query(filters.regex("^sub_json_import$") & is_auth_query())
async def sub_json_import_handler(client, query):
  user_id = query.from_user.id
  IMPORT_STATE[user_id] = time.time()

  await retry_on_flood(query.message.edit_text)(
    "<b><blockquote>📤 Please send your Subscriptions JSON file within 60 seconds...</blockquote></b>",
    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" 𝘊𝘢𝘯𝘤𝘦𝘭 ", callback_data=f"isubs:1")]])
  )


@Bot.on_message(filters.document & filters.private)
async def handle_import_doc(client, message):
  user_id = message.from_user.id
  logger.info(user_id)
  if user_id not in IMPORT_STATE:
    return message.continue_propagation()

  if time.time() - IMPORT_STATE[user_id] > 60:
    if user_id in IMPORT_STATE: del IMPORT_STATE[user_id]
    return await retry_on_flood(message.reply)("<b>Timeout! Please click the import button again.</b>")

  if user_id in IMPORT_STATE:
    del IMPORT_STATE[user_id]

  eff_user_id = get_effective_user_id(user_id)

  if not message.document.file_name.endswith(".json"):
    return await message.reply("<b>Invalid file type. Please send a .json file.</b>")

  sts = await message.reply("<code>Importing data...</code>")

  import json
  import os

  file_path = None
  try:
    file_path = await client.download_media(message)
    if not file_path:
      return await retry_on_flood(sts.edit)("<b>Failed to download the file.</b>")

    with open(file_path, 'r') as f:
      data = json.load(f)

    if not isinstance(data, dict):
      return await retry_on_flood(sts.edit)("<b>Invalid JSON format. Expected a dictionary.</b>")

    valid_keys = ["subs", "subscriptions"]
    if not any(key in data for key in valid_keys):
      return await retry_on_flood(sts.edit)("<b>No valid subscription data found in the JSON file.</b>")

    success = await database.update_user_data(eff_user_id, data)
    if success:
      await retry_on_flood(sts.edit)("<b>Subscriptions imported successfully!</b>")
    else:
      await retry_on_flood(sts.edit)("<b>Failed to import data. The database could not be updated.</b>")

  except Exception as e:
    logger.exception(e)
    await retry_on_flood(sts.edit)(f"<b>Error during import: {e}</b>")
    
  finally:
    if file_path and os.path.exists(file_path):
      try:
        os.remove(file_path)
      except OSError as e:
        logger.warning(f"Failed to remove temp import file {file_path}: {e}")


@Bot.on_callback_query(filters.regex("^sub_import$") & is_auth_query())
async def sub_import_handler(client, query):
  await query.answer("Instructions sent!", show_alert=True)
  await query.message.reply_text(
    "<b>To import your Subscriptions:\n\n1. Reply to your exported JSON file with <code>/import</code> command.\n2. The bot will automatically update your subscriptions.</b>",
  )

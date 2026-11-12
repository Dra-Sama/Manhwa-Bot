# Code By @V_Sbotmaker (on Telegram)
import random
from pyrogram import filters
from pyrogram.types import (
   Chat, InlineKeyboardButton, InlineKeyboardMarkup, 
   InputMediaDocument, InputMediaPhoto, Message
)

from TG.storage import (
   retry_on_flood, igrone_error, split_list, 
   get_episode_number, Listeing_cache
)

from bot import Bot, Vars, logger
from Tools.db import database

from Tools.uploaders import (
  get_chat, Uploader, clean_text_ as clean_text, 
  update_notify, get_target_auto_channel
)

from pyrogram.enums import ChatMemberStatus
from copy import deepcopy


PAGE_SIZE = 15

cache_handle_type = {
  "a": "auto_channels",
  "t": "target_channels"
}


def iterate_(data: list, page: int = 1):
  try:
    page = int(page)
  except Exception:
    page = 1

  if not data or page < 1:
    return []

  start = (page - 1) * PAGE_SIZE
  return data[start:start + PAGE_SIZE]


async def get_target_markup(user_id: str, handle_type: str, page: int = 1):

    try:
      page = int(page)
    except Exception:
      page = 1

    if page < 1:
      page = 1

    button = []

    target_, auto_ = await get_target_auto_channel(user_id)

    data = deepcopy(target_) if handle_type.startswith("t") else deepcopy(auto_)

    del target_, auto_

    handle_type = handle_type.replace("_", " ")

    label = "Auto Update" if handle_type.startswith("a") else "Auto Upload"
    txt = f"<b>{label} Channels</b>\n\n"

    handle_type = handle_type[0]

    
    offset = (page - 1) * PAGE_SIZE
    page_items = iterate_(data, page)

    for i, channel_id in enumerate(page_items, start=offset):

      channel_ = await get_chat(channel_id)
      channel_name = channel_.title if channel_ else channel_id

      if isinstance(channel_, Chat):
        channel_link = channel_.invite_link

        if channel_link:
          txt += f"{i}. <a href='{channel_link}'>{channel_name}</a>\n"
        else:
          txt += f"{i}. {channel_name}\n"

      else:
        txt += f"{i}. {channel_name} [Not Added]\n"

      button.append(InlineKeyboardButton(f"{i}", callback_data=f"tin_{i}:{handle_type}:{page}"))

    button = split_list(button)

    button.append([
      InlineKeyboardButton(f" 𝘛𝘰𝘵𝘢𝘭 𝘊𝘩𝘢𝘯𝘯𝘦𝘭𝘴: {len(data)}", callback_data="just_kidding"),
      InlineKeyboardButton(f" 𝘗𝘢𝘨𝘦 𝘕𝘰: {page}", callback_data="just_kidding")
    ])

    arrow = []
    if iterate_(data, page=page - 5):
      arrow.append(
        InlineKeyboardButton("<5x", callback_data=f"tr:{page - 5}:{handle_type}")
      )

    if iterate_(data, page=page - 2):
      arrow.append(
          InlineKeyboardButton("<2x", callback_data=f"tr:{page - 2}:{handle_type}")
      )

    if iterate_(data, page=page - 1):
        arrow.append(
            InlineKeyboardButton("<<", callback_data=f"tr:{page - 1}:{handle_type}")
        )

    if iterate_(data, page=page + 1):
        arrow.append(
            InlineKeyboardButton(">>", callback_data=f"tr:{page + 1}:{handle_type}")
        )

    if iterate_(data, page=page + 2):
      arrow.append(
          InlineKeyboardButton("2X>", callback_data=f"tr:{page + 2}:{handle_type}")
      )

    if iterate_(data, page=page + 5):
      arrow.append(
          InlineKeyboardButton("5x>", callback_data=f"tr:{page + 5}:{handle_type}")
      )

    if arrow:
        button.append(arrow)

    extra_button = [
      [
        InlineKeyboardButton(" + 𝘈𝘥𝘥 + ", callback_data=f"tadd:{handle_type}"),
        InlineKeyboardButton("- 𝘙𝘦𝘮𝘰𝘷𝘦 𝘈𝘭𝘭 -", callback_data=f"trm:all:{handle_type}")
      ],
      [
        InlineKeyboardButton(" 𝘙𝘦𝘧𝘳𝘦𝘴𝘩 ", callback_data=f"tr:{page}:{handle_type}"),
        InlineKeyboardButton(" 𝘐𝘮𝘱𝘰𝘳𝘵 ", callback_data=f"timport:{'a' if handle_type != 'a' else 't'}")
      ],
      [
        InlineKeyboardButton(" ⇦ 𝘉𝘢𝘤𝘬 ", callback_data="mus"),
        InlineKeyboardButton(" ✵ 𝘊𝘭𝘰𝘴𝘦 ✵ ", callback_data="close")
      ]
    ]
    button.extend(extra_button)

    return button, txt


REPLY_FORMAT_TXT = """
<b>Reply to a document to replace and need give replace post link also..

Format: <code>/replace <link or Channel id/post id></code>

<u>For Example</u>
<code>/replace https://t.me/c/34877631/002</code>
<code>/replace Wizard_Bots/002</code>

<u>Note</u>: <blockquote>Need to Reply with New Document</blockquote></b>"""


@Bot.on_message(filters.command(["replace"]))
async def replace_(client, message):
  if (Vars.IS_PRIVATE) and (message.chat.id not in Vars.ADMINS):
    return await retry_on_flood(message.reply)("<code>You cannot use me baby </code>")

  replace_link = message.text.split(" ", 1)
  new_doc = message.reply_to_message

  if not new_doc or len(replace_link) <= 1:
    return await retry_on_flood(message.reply)(REPLY_FORMAT_TXT)

  try:
    new_doc = new_doc.document or new_doc.photo or new_doc.video or new_doc.audio or new_doc.voice or new_doc.video_note or new_doc.sticker or new_doc.animation or new_doc.document
    try:
      caption = message.reply_to_message.caption
    except Exception:
      caption = ""

    split_link = str(replace_link[-1]).split("/")
    channel_id_username = split_link[-2]
    post_id = int(split_link[-1])
    try:
      channel_id_username = int(channel_id_username)
      channel_id_username = "-100" + str(channel_id_username)
      channel_id_username = int(channel_id_username)
    except Exception:
      channel_id_username = channel_id_username

    if channel_id_username not in (message.chat.id, message.chat.username):
      member = await retry_on_flood(Bot.get_chat_member)(channel_id_username, message.from_user.id)

      if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        return await retry_on_flood(message.reply)("<code>You are not admin of this channel</code>")

  except Exception:
    return await retry_on_flood(message.reply)(REPLY_FORMAT_TXT)

  sts = await retry_on_flood(message.reply)("<code>Processing...</code>")
  try:
    await Bot.edit_message_media(
      chat_id=channel_id_username,
      media=InputMediaDocument(new_doc.file_id, caption=caption),
      message_id=post_id,
    )
    await retry_on_flood(sts.edit)("<code>Replaced</code>")
  except Exception as e:
    logger.exception(e)
    await retry_on_flood(sts.edit)(f"<code>Error: {e}</code>")



@Bot.on_callback_query(filters.regex("^(target_channel|auto_channel)$"))
async def target_channel_(client, callback):
  if not Vars.AUTO_F:
    return await retry_on_flood(callback.answer)("Auto Upload is Disabled", show_alert=True)

  if (Vars.IS_PRIVATE) and (callback.message.chat.id not in Vars.ADMINS):
    return await retry_on_flood(callback.answer)("<code>You cannot use me baby </code>")

  await database.ensure_user(callback.from_user.id)
  handle_type = callback.data[0]
  button, txt = await get_target_markup(str(callback.from_user.id), handle_type)

  rand_pics = random.choice(Vars.PICS)
  await retry_on_flood(callback.edit_message_media)(
    InputMediaPhoto(rand_pics, caption=txt),
    reply_markup=InlineKeyboardMarkup(button)
  )


@Bot.on_callback_query(filters.regex("^tr:")) # tr:{page+1}:{handle_type}
async def target_channel_cb_(client, query):
  split_data = query.data.split(":")

  if len(split_data) == 3:
    page, handle_type = split_data[-2], split_data[-1]
  else:
    await igrone_error(query.answer)("This is an old button, please click at refresh", show_alert=True)
    return

  try:
    page = int(page)
  except Exception:
    page = 1

  await database.ensure_user(query.from_user.id)
  button, txt = await get_target_markup(str(query.from_user.id), handle_type, page)

  await igrone_error(query.answer)()

  await retry_on_flood(query.edit_message_media)(
    InputMediaPhoto(random.choice(Vars.PICS), caption=txt),
    reply_markup=InlineKeyboardMarkup(button)
  )


@Bot.on_callback_query(filters.regex("^tadd:")) # tadd:{handle_type}
async def target_channel_add_(client, query):
  str_id = str(query.from_user.id)

  try:
    handle_type = query.data.split(":")[-1]
    handle_type = handle_type[0]
  except Exception:
    handle_type = "t"

  handle_type = cache_handle_type.get(handle_type, "target_channels")
  await database.ensure_user(query.from_user.id)

  await retry_on_flood(query.answer)()
  listener_id = await retry_on_flood(query.edit_message_text)(
    "<b>Send me the channel username or Channel ID or Forward Message from Channel.\n\nYou can Send Mutiple at Once , Bot will Add all target channel in db \n\nStop Listing By using /stop</b>",
  )
  Listeing_cache[str_id] = (listener_id, handle_type)


@Bot.on_message((filters.private |  filters.forwarded) & ~filters.regex(r"/"))
async def target_channel_add_text_(client, message: Message):
  if not Vars.AUTO_F:
    return message.continue_propagation()

  try:
    str_id = str(message.from_user.id)
    if str_id not in Listeing_cache:
      return message.continue_propagation()
  except Exception:
    return message.continue_propagation()

  listener_id, handle_type = Listeing_cache[str_id]

  await database.ensure_user(str_id)

  target_, auto_ = await get_target_auto_channel(str_id)

  check_channel_list = deepcopy(target_) if handle_type == "target_channels" else deepcopy(auto_)
  del target_, auto_

  if message.forward_from_chat:
    channel_id = int(message.forward_from_chat.id)

  else:
    try:
      channel_id = int(message.text)
    except Exception:
      channel_id = str(message.text)

  member = await retry_on_flood(Bot.get_chat_member)(channel_id, message.from_user.id)

  if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
    await retry_on_flood(message.reply)("<code>You are not admin of this channel</code>")
    return

  channel_info = await get_chat(channel_id)
  if not channel_info or not isinstance(channel_info, Chat):
    await retry_on_flood(message.reply_text)(
      "<b><i>Add Bot in Channel With Full Right</i></b>"
    )
    return

  if channel_id not in check_channel_list:
    await database.add_channel(str_id, handle_type, channel_info.id)

    await retry_on_flood(message.reply_text)(
      f"<b>Channel Added: {channel_id}</b>"
    )

  else:
    await retry_on_flood(message.reply_text)(
      f"<b>Channel Already Added: {channel_id}</b>"
    )


@Bot.on_message(filters.command("stop") & filters.private)
async def stop_listening_(client, message):
  str_id = str(message.from_user.id)
  await database.ensure_user(str_id)
  if str_id not in Listeing_cache:
    return await retry_on_flood(message.reply_text)("<b>Bot Restarted!, Try Again ;- /us </b>")

  sts = await retry_on_flood(message.reply_text)("`Processing...`")
  try:
    listener_id, handle_type = Listeing_cache.pop(str_id)
    button, txt = await get_target_markup(str_id, handle_type)
    ran_pics = random.choice(Vars.PICS)

    try:
      await retry_on_flood(message.reply_photo)(
        ran_pics, caption=txt,
        reply_markup=InlineKeyboardMarkup(button),
      )
    except Exception:
      await retry_on_flood(message.reply_photo)(
        Vars.PICS[0], caption=txt,
        reply_markup=InlineKeyboardMarkup(button),
      )

    await retry_on_flood(Bot.delete_messages)(
      int(str_id), int(listener_id.id)
    )
    await retry_on_flood(sts.delete)()
  except Exception as err:
    logger.exception(err)
    await retry_on_flood(sts.edit)(f"`Error: {err}`")


@Bot.on_callback_query(filters.regex("^timport:")) # timport:{handle_type}
async def target_channel_import_(client, query):
  try:
    handle_type = query.data.split(":")[-1]
    handle_type = handle_type[0]
  except Exception:
    handle_type = "t"

  str_id = str(query.from_user.id)
  await database.ensure_user(str_id)

  handle_type = cache_handle_type.get(handle_type, "target_channels")
  target_channels, auto_channels = await get_target_auto_channel(str_id)

  if handle_type == "target_channels":
    handle_type = "auto_channels"
    existing = set(auto_channels)
    import_list = [c for c in target_channels if c not in existing]
    
  else:
    handle_type = "target_channels"
    existing = set(target_channels)
    import_list = [c for c in auto_channels if c not in existing]

  if not import_list:
    await igrone_error(query.answer)(" Cannot Import, Not Found ")

  try:
    for channel_id in import_list:
      await database.add_channel(str_id, handle_type, channel_id)

    await igrone_error(query.answer)(f" {len(import_list)} Channels Imported ")

    button, txt = await get_target_markup(str(query.from_user.id), handle_type)

    await igrone_error(query.answer)()
    await retry_on_flood(query.edit_message_media)(
      InputMediaPhoto(random.choice(Vars.PICS), caption=txt),
      reply_markup=InlineKeyboardMarkup(button)
    )
  except Exception:
    await igrone_error(query.answer)(" Error Occured ")


@Bot.on_callback_query(filters.regex("^tin_")) # tin_{channel_range}:{handle_type}:{page}
async def target_channel_info_(client, query):
  channel_range = query.data.split("_", 1)[-1]
  await database.ensure_user(query.from_user.id)
  page = 1

  if ":" in channel_range:
    channel_range, handle_type, page = channel_range.split(":")

  else:
    handle_type = "t"

  handle_type = cache_handle_type.get(handle_type, "target_channels")
  channel_range = int(channel_range)

  target_, auto_ = await get_target_auto_channel(str(query.from_user.id))
  check_channels = deepcopy(target_) if handle_type.startswith("t") else deepcopy(auto_)

  del target_, auto_

  try:
    channel_id = check_channels[channel_range]

  except Exception:
    channel_id = "Not Found"

  channel_info_text = f"<b> Channel Info:- <code>{channel_id}</code>\n\n"
  try:
    channel_info = await Bot.get_chat(channel_id)
    channel_info_text += f"Channel Name:- <code>{channel_info.title}</code>\n"
    channel_info_text += f"Mode:- <code>{handle_type}</code>\n"

    if isinstance(channel_info, Chat):
      channel_info_text += f"Full Name:- <code>{channel_info.full_name}</code>\n"
      channel_info_text += f"Username:- <code>{channel_info.username}</code>\n"
      channel_info_text += f"ID:- <code>{channel_info.id}</code>\n"
      channel_info_text += f"Bio:- <code>{channel_info.bio}</code>\n"
      channel_info_text += f"DC:- <code>{channel_info.dc_id}</code>\n"
      channel_info_text += f"Invite Link:- <code>{channel_info.invite_link}</code>\n"
      channel_info_text += f"Status:- <code>{'Joined' if channel_info.invite_link else 'Not Joined'}</code>\n"
    else:
      channel_info_text += "Status:- <code>Not Join</code>\n"

  except Exception:
    channel_info_text += "Status:- <code>Not Join</code>\n"

  channel_info_text += "</b>"

  await igrone_error(query.answer)()

  button = InlineKeyboardMarkup([
    [
      InlineKeyboardButton(" 𝘚𝘦𝘵𝘵𝘪𝘯𝘨𝘴 ", callback_data="mus"),
      InlineKeyboardButton(" 𝘙𝘦𝘮𝘰𝘷𝘦 ", callback_data=f"trm:{channel_range}:{handle_type[0]}:{page}")
    ],
    [
      InlineKeyboardButton("⇦ 𝗕𝗔𝗖𝗞", callback_data=f"tr:{page}:{handle_type}"), 
      InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="kclose")
    ]
  ])

  await retry_on_flood(query.edit_message_media)(
    InputMediaPhoto(random.choice(Vars.PICS), caption=channel_info_text),
    reply_markup=button
  )


@Bot.on_callback_query(filters.regex("^trm")) #trm:{channel_range}:{handle_type}:{page}
async def target_channel_remove_(client, query):
  logger.info(query.data)
  split_str = query.data.split(":")

  page = 1

  if len(split_str) == 4:
    channel_range, handle_type, page = split_str[-3], split_str[-2], split_str[-1]

  elif len(split_str) == 3:
    channel_range, handle_type, page = split_str[-2], split_str[-1], 1

  else:
    channel_range, handle_type, page = split_str[-1], "t", 1

  try:
    page = int(page)
  except Exception:
    page = 1

  handle_type = cache_handle_type.get(handle_type, "target_channels")
  await database.ensure_user(query.from_user.id)

  try:
    channel_range = int(channel_range)
  except Exception:
    channel_range = channel_range

  str_id = str(query.from_user.id)

  if channel_range == "all":
    await database.erase_channel(str_id, handle_type)

    await retry_on_flood(query.answer)("All Channel Removed")

  else:
    try:
      target_, auto_ = await get_target_auto_channel(str_id)
      check_channel_list = deepcopy(target_) if handle_type == "target_channels" else deepcopy(auto_)
      del target_, auto_

      channel_id = check_channel_list[channel_range]

      if Vars.IS_PRIVATE:
        user_id = await database.check_dump(channel_id)
      else:
        user_id = str_id

      if not user_id:
        await igrone_error(query.answer)("Users  Not Found")
        return

      await database.remove_channel(user_id, handle_type, channel_id)

      await retry_on_flood(query.answer)("Channel Removed")
    except Exception:
      await retry_on_flood(query.answer)("Channel Not Found")

  button, txt = await get_target_markup(str(query.from_user.id), handle_type, page)

  await igrone_error(query.answer)()
  await retry_on_flood(query.edit_message_media)(
    InputMediaPhoto(random.choice(Vars.PICS), caption=txt),
    reply_markup=InlineKeyboardMarkup(button),
  )


@Bot.on_message(filters.document & ~filters.private)
async def target_channel_forward_(client, message):
  if not Vars.AUTO_F:
    return message.continue_propagation()

  channel_id = message.chat.id
  user_id = await database.check_dump(channel_id)

  file_name = message.document.file_name
  try:
     search_name = message.caption
  except Exception:
    search_name = file_name

  if search_name in ["None", "none", None]:
    search_name = file_name

  original_ep_num = str(get_episode_number(file_name))

  # Only fetch auto_channels if we have a valid user_id
  if user_id:
    auto_channels = await database.get_auto_channel(str(user_id))
    if channel_id in auto_channels:
      try:
        channel_info = await get_chat(channel_id)
      except Exception:
        channel_info = None

      if not channel_info:
        return

      logger.info(f"Auto updating {search_name} {original_ep_num}")
      await update_notify(
        post_info=message, user_id=user_id,
        manga_title=message.chat.title, episode_number=original_ep_num,
        channel_info=channel_info
      )
      return

  all_dump_channel = []
  try:
    if Vars.IS_PRIVATE:
      async for user_info in database.get_users():
        if "setting" not in user_info:
          user_info['setting'] = {}

        if dump_ := user_info["setting"].get("dump", None):
          all_dump_channel.append(dump_)

      if Vars.CONSTANT_DUMP_CHANNEL:
        all_dump_channel.append(Vars.CONSTANT_DUMP_CHANNEL)

    elif user_id:
      dump_ = (await database.get_settings(user_id)).get("dump", None)
      if dump_:
        all_dump_channel.append(dump_)

  except Exception as err:
    logger.exception(err)
    return message.continue_propagation()

  if channel_id not in all_dump_channel:
    return message.continue_propagation()

  # For IS_PRIVATE mode: find the owner of this dump channel
  if Vars.IS_PRIVATE and not user_id:
    async for user_info in database.get_users():
      if user_info.get("setting", {}).get("dump") == channel_id:
        user_id = str(user_info["_id"])
        break
    if not user_id:
      logger.warning(f"Could not find owner for dump channel {channel_id}")
      return message.continue_propagation()

  if not user_id:
    return message.continue_propagation()

  search_name = str(search_name).lower().strip()
  search_name = search_name.replace(str(original_ep_num), "")
  search_name = clean_text(search_name)
  search_name = search_name.lower().strip()
  logger.debug(f" Processing {search_name} {original_ep_num} ")
  
  try:
    await Uploader().upload_to_targets_channels(
      docs=message, original_ep_num=original_ep_num,
      search_name=search_name, user_id=str(user_id),
    )
  except Exception as e:
    logger.exception(e)
    
    await igrone_error(Bot.send_message)(
      Vars.LOG_CHANNEL, f"Error: `{e}`"
    ) if Vars.LOG_CHANNEL else None

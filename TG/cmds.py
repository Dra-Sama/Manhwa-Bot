# Code By @V_Sbotmaker (on Telegram)
from pyrogram import filters
from pyrogram.errors import FloodWait
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, CallbackQuery

from .storage import *
import pyrogram.errors

from bot import Bot, Vars, logger, Manhwa_Bot

import random
from Tools.db import database, get_effective_user_id
from Tools.my_token import verify_token

import time

from asyncio import create_subprocess_exec
from os import execl
from sys import executable

import shutil, time, os, platform
import asyncio
import psutil

import json 

from io import BytesIO
from copy import deepcopy
import subprocess


HELP_MSG = """
<blockquote>Tᴏ ᴅᴏᴡɴʟᴏᴀᴅ ᴀ ᴍᴀɴɢᴀ ᴊᴜsᴛ ᴛʏᴘᴇ ᴛʜᴇ ɴᴀᴍᴇ ᴏғ ᴛʜᴇ ᴍᴀɴɢᴀ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴋᴇᴇᴘ ᴜᴘ ᴛᴏ ᴅᴀᴛᴇ..</blockquote>

For example: `One Piece`

<blockquote>Tʜᴇɴ ʏᴏᴜ ᴡɪʟʟ ʜᴀᴠᴇ ᴛᴏ ᴄʜᴏᴏsᴇ ᴛʜᴇ ʟᴀɴɢᴜᴀɢᴇ ᴏғ ᴛʜᴇ ᴍᴀɴɢᴀ. Dᴇᴘᴇɴᴅɪɴɢ ᴏɴ ᴛʜɪs ʟᴀɴɢᴜᴀɢᴇ, ʏᴏᴜ ᴡɪʟʟ ʙᴇ ᴀʙʟᴇ ᴛᴏ ᴄʜᴏᴏsᴇ ᴛʜᴇ ᴡᴇʙsɪᴛᴇ ᴡʜᴇʀᴇ ʏᴏᴜ ᴄᴏᴜʟᴅ ᴅᴏᴡɴʟᴏᴀᴅ ᴛʜᴇ ᴍᴀɴɢᴀ. Hᴇʀᴇ ʏᴏᴜ ᴡɪʟʟ ʜᴀᴠᴇ ᴛʜᴇ ᴏᴘᴛɪᴏɴ ᴛᴏ sᴜʙsᴄʀɪʙᴇ, ᴏʀ ᴛᴏ ᴄʜᴏᴏsᴇ ᴀ ᴄʜᴀᴘᴛᴇʀ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ. Tʜᴇ ᴄʜᴀᴘᴛᴇʀs ᴀʀᴇ sᴏʀᴛᴇᴅ ᴀᴄᴄᴏʀᴅɪɴɢ ᴛᴏ ᴛʜᴇ ᴡᴇʙsɪᴛᴇ..</blockquote>

<blockquote><b>Updates Channel : @Manga_Cruise</b></blockquote>
"""
start_text = """<blockquote>🌸 ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ᴍᴀɴɢᴀ ʙᴏᴛ!!</blockquote>

<blockquote><b>📖 ᴊᴜsᴛ sᴇɴᴅ ᴍᴇ ᴀɴʏ ᴍᴀɴɢᴀ / ᴍᴀɴʜᴡᴀ ɴᴀᴍᴇ ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ!</b></blockquote>

<blockquote>⚙️ ᴜsᴇ /ᴜs ᴛᴏ ᴄᴜsᴛᴏᴍɪᴢᴇ ʏᴏᴜʀ sᴇᴛᴛɪɴɢs
🔔 ᴜsᴇ /sᴜʙs ᴛᴏ ᴠɪᴇᴡ ʏᴏᴜʀ sᴜʙsᴄʀɪᴘᴛɪᴏɴs</blockquote>"""

Start_Button = [
  [
    InlineKeyboardButton("⚙️ 𝚂𝚎𝚝𝚝𝚒𝚗𝚐𝚜", callback_data="mus"),
    InlineKeyboardButton("📋 𝚀𝚞𝚎𝚞𝚎", callback_data="refresh_queue")
  ],
  [
    InlineKeyboardButton("🔔 𝚂𝚞𝚋𝚜𝚌𝚛𝚒𝚋𝚎𝚜", callback_data="isubs:1"),
    InlineKeyboardButton("❓ 𝙷𝚎𝚕𝚙", callback_data="help")
  ], 
  [
    InlineKeyboardButton("✖ 𝗖𝗟𝗢𝗦𝗘", callback_data="kclose"),
  ]
]
help_button = deepcopy(Start_Button)
help_button[-1][0] = InlineKeyboardButton("🏠 ʜᴏᴍᴇ", callback_data="home")






@Bot.on_callback_query(filters.regex("^home$"))
@Bot.on_message(filters.command("start"))
async def start(client, message):
  try:
    if Vars.IS_PRIVATE and message.chat.id not in Vars.ADMINS:
        return await message.reply("<code>hii </code>")
    
    await database.ensure_user(message.from_user.id)
  except Exception:
    pass 
  
  try:
    if len(message.command) > 1:
      if message.command[1] != "start":
        user_id = message.from_user.id
        token = message.command[1]
        sts = await retry_on_flood(message.reply)("<i>ㅤProcessing.....</i>")
        return await verify_token(sts, user_id, token)
        
  except Exception:
    pass

  photo = random.choice(Vars.PICS)
  ping = time.strftime("%HH %Mm %Ss", time.gmtime(time.time() - Vars.PING))
  if isinstance(message, CallbackQuery):
    try:
      await retry_on_flood(message.edit_message_media)(
        media=InputMediaPhoto(photo, caption=start_text.format(ping)),
        reply_markup=InlineKeyboardMarkup(Start_Button)
      )
    except Exception:
      await retry_on_flood(message.edit_message_media)(
        media=InputMediaPhoto(Vars.PICS[-1], caption=start_text.format(ping)),
        reply_markup=InlineKeyboardMarkup(Start_Button),
      )
      
  else:
    try:
      await retry_on_flood(message.reply_photo)(
        photo,
        caption=start_text.format(ping),
        reply_markup=InlineKeyboardMarkup(Start_Button),
      )
    except Exception:
      await retry_on_flood(message.reply_photo)(
        Vars.PICS[-1],
        caption=start_text.format(ping),
        reply_markup=InlineKeyboardMarkup(Start_Button),
      )


@Bot.on_message(filters.private)
async def on_private_message(client, message):
  if str(message.from_user.id) in Listeing_cache:
    return message.continue_propagation()

  if message.from_user.id in client.listerner:
    return message.continue_propagation()
    
  channel = Vars.FORCE_SUB_CHANNEL
  try:
    if channel in ["None", None, "none", "OFF", False, "False", ""]:
      return message.continue_propagation()
    
    if not client.FSB or client.FSB == []:
      return message.continue_propagation()
    
    channel_button, change_data = await check_fsb(client, message)
    if not channel_button:
      return message.continue_propagation()
    
    channel_button = split_list(channel_button)
    channel_button.append([InlineKeyboardButton("𝗥𝗘𝗙𝗥𝗘𝗦𝗛 ⟳", callback_data="refresh")])
    
    await retry_on_flood(message.reply_photo)(
      caption=Vars.FORCE_SUB_TEXT,
      photo=random.choice(Vars.PICS),
      reply_markup=InlineKeyboardMarkup(channel_button),
    )
    if change_data:
      for change_ in change_data:
        client.FSB[change_[0]] = (change_[1], change_[2], change_[3])
  except Exception:
    return message.continue_propagation()


@Bot.on_message(filters.command("export"))
async def export_data(client, message):
  if not await database.is_authorized(message.from_user.id):
    return await message.reply("<b>This bot is restricted. Only admins or premium users can use it.</b>")

  user_id = get_effective_user_id(message.from_user)
  data = await database.get_full_user_data(user_id)

  if not data:
    return await message.reply("<b>No data found to export.</b>")

  json_data = json.dumps(data, indent=2)
  bio = BytesIO(json_data.encode('utf-8'))
  bio.name = f"user_data_{user_id}.json"

  await retry_on_flood(message.reply_document)(
    document=bio,
    caption="<b>Here is your exported data file.</b>",
  )

@Bot.on_message(filters.command("import"))
async def import_data(client, message):
  if not await database.is_authorized(message.from_user.id):
    return await message.reply("<b>This bot is restricted. Only admins or premium users can use it.</b>")

  reply = message.reply_to_message
  if not reply or not reply.document:
    return await message.reply("<b>Please reply to a JSON file with /import to restore your data.</b>")

  if not reply.document.file_name.endswith(".json"):
    return await message.reply("<b>Invalid file type. Please provide a .json file.</b>")

  sts = await message.reply("<code>Importing data...</code>")
  eff_user_id = get_effective_user_id(message.from_user)

  try:
    file_path = await client.download_media(reply)
    with open(file_path, 'r') as f:
      data = json.load(f)
    os.remove(file_path)

    if not isinstance(data, dict):
      return await retry_on_flood(sts.edit)("<b>Invalid JSON format. Expected a dictionary.</b>")

    valid_keys = ["subs", "subscriptions", "target_channels", "auto_channels"]
    if not any(key in data for key in valid_keys):
      return await retry_on_flood(sts.edit)("<b>No valid data found in the JSON file.</b>")

    success = await database.update_user_data(eff_user_id, data)
    if success:
      await retry_on_flood(sts.edit)("<b>Data imported successfully!</b>")
    else:
      await retry_on_flood(sts.edit)("<b>Failed to import data. The database could not be updated.</b>")

  except Exception as e:
    # logger.exception(e)  # Fallback if logger is not in scope
    await retry_on_flood(sts.edit)(f"<b>Error during import: {e}</b>")
  



@Bot.on_message(filters.command("my_plan"))
async def my_plan(client, message):
  plan = await database.premium_user(message.from_user.id)
  if plan:
    xt = (plan["expiration_timestamp"] - (time.time()))
    x = round(xt / (24 * 60 * 60))
  
    await retry_on_flood(message.reply)(
      f"""
<i>Your Information:</i>

  <b>- User ID: {message.from_user.id}</b>
  <b>- Username: {message.from_user.username}</b>
  <b>- Days: {plan.get("Days", "")}</b>
  <b>- Expiration Days: {x}</b> 

<i>Thanks For Buying It......</i>""",
      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="kclose")]])
    )
    
  else:
    await retry_on_flood(message.reply)(
      "<i> You Have No Plan!! </i>",
      reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton(" Buy Now ", callback_data="premuim")]
      ]))




@Bot.on_message(filters.command(["clean_tasks", "clean_queue"]))
async def deltask(client, message):
  if Vars.IS_PRIVATE:
    if message.chat.id not in Vars.ADMINS:
      return await message.reply("<code>You cannot use me baby </code>")

  if queue.get_count(message.from_user.id):
    numb = await queue.delete_tasks(message.from_user.id)
    await message.reply(f"<i>All Your Tasks Deleted:- {numb} </i>")
  else:
    await message.reply("<i>There is no any your pending tasks.... </i>")






@Bot.on_message(filters.command(["add_premium", "add_admin"]))
async def add_handler(_, msg):
  if msg.from_user.id not in Vars.ADMINS:
    return

  sts = await msg.reply_text("<code>Processing...</code>")
  try:
    user_id = int(msg.text.split(" ")[1])
    if msg.text == "/add_premium":
      time_limit_days = int(msg.text.split(" ")[2])
      await database.add_premium(user_id, time_limit_days)
      await retry_on_flood(sts.edit)("<code>User added to premium successfully.</code>")
      try:
        await retry_on_flood(_.send_message)(
          user_id,
          f"<i>You are now a premium user for {time_limit_days} days... Thanks For Buying It.....</i>"
        )
      except Exception:
        pass

    else:
      Vars.ADMINS.append(user_id)
      await retry_on_flood(sts.edit)("<code>User added to admin successfully.</code>")
      
  except Exception as err:
    await retry_on_flood(sts.edit)(err)




@Bot.on_message(filters.command(["del_premium"]))
async def del_handler(_, msg):
  if msg.from_user.id not in Vars.ADMINS:
    return
  
  sts = await msg.reply_text("<code>Processing...</code>")
  try:
    user_id = int(msg.text.split(" ")[1])
    await database.remove_premium(user_id)
    await retry_on_flood(sts.edit)("<code>User removed from premium successfully.</code>")
    try:
      await retry_on_flood(_.send_message)(
        user_id,
        "<i>Your Premuims Plans End.. Please Buy again or Contact To Owner....  .</i>"
      )
    except Exception:
      pass
    
  except Exception as err:
    await retry_on_flood(sts.edit)(err)




@Bot.on_message(filters.command(["del_expired", "del_expired_premium"]))
async def del_expired_handler(_, msg):
  if msg.from_user.id not in Vars.ADMINS:
    return
  
  sts = await msg.reply_text("<code>Processing...</code>")
  try:
    await database.remove_expired_users()
    await retry_on_flood(sts.edit)("<code>Expired users removed successfully.</code>")
  except Exception as err:
    await retry_on_flood(sts.edit)(err)




@Bot.on_message(filters.command(["premium", "premium_users"]))
async def premium_handler(_, msg):
  if msg.from_user.id not in Vars.ADMINS:
    return
    
  sts = await msg.reply_text("<code>Processing...</code>")
  try:
    txt = "<b>Premium Users:-</b>\n"
    async for user_ids, data in database.get_all_premium():
      try:
        user_info = await _.get_users(user_ids)
        username = user_info.username
        first_name = user_info.first_name
      except Exception:
        username = "N/A"
        first_name = "N/A"

      expiration_timestamp = data["expiration_timestamp"]
      xt = (expiration_timestamp - (time.time()))
      x = round(xt / (24 * 60 * 60))
      txt += f"User id: <code>{user_ids}</code>\nUsername: @{username}\nName: <code>{first_name}</code>\nExpiration Timestamp: {x} days\n"

    await retry_on_flood(sts.edit)(txt[:1024])
  except Exception as err:
    await retry_on_flood(sts.edit)(err)


@Bot.on_message(filters.command(["broadcast", "b"]))
async def b_handler(_, msg):
  if msg.from_user.id not in Vars.ADMINS:
    return
  
  return await borad_cast_(_, msg)


@Bot.on_message(filters.command(["pbroadcast", "pb"]))
async def pb_handler(_, msg):
  if msg.from_user.id not in Vars.ADMINS:
    return
  
  return await borad_cast_(_, msg, pin=True)

@Bot.on_message(filters.command(["forward", "fd"]))
async def fb_handler(_, msg):
  if msg.from_user.id not in Vars.ADMINS:
    return
  
  return await borad_cast_(_, msg, forward=True)

@Bot.on_message(filters.command(["pforward", "pfd"]))
async def pfb_handler(_, msg):
  if msg.from_user.id not in Vars.ADMINS:
    return
  
  return await borad_cast_(_, msg, pin=True, forward=True)

async def borad_cast_(_, message, pin=None, forward=None):
  sts = await message.reply_text("<code>Processing...</code>")
  if message.reply_to_message:
    msg = message.reply_to_message
    total = 0
    successful = 0
    blocked = 0
    deleted = 0
    unsuccessful = 0
    
    await retry_on_flood(sts.edit)("<code>Broadcasting...</code>")
    
    async for user_data in database.get_users():
      try:
        user_id = user_data.get("_id")
        if not user_id:
          continue
        
        if forward:
          docs = await retry_on_flood(msg.forward)(int(user_id))
        else:
          docs = await retry_on_flood(msg.copy)(int(user_id))
          
        if pin:
          await retry_on_flood(docs.pin)(both_sides=True)

        successful += 1
      
      except pyrogram.errors.UserIsBlocked:
        blocked += 1
      except pyrogram.errors.PeerIdInvalid:
        unsuccessful += 1
      except pyrogram.errors.InputUserDeactivated:
        deleted += 1
      except pyrogram.errors.UserNotParticipant:
        blocked += 1
      except Exception:
        unsuccessful += 1

    status = f"""<b><u>Broadcast Completed</u>

Total Users: <code>{total}</code>
Successful: <code>{successful}</code>
Blocked Users: <code>{blocked}</code>
Deleted Accounts: <code>{deleted}</code>
Unsuccessful: <code>{unsuccessful}</code></b>"""

    await retry_on_flood(sts.edit)(status)
  else:
    await retry_on_flood(sts.edit)("<code>Reply to a message to broadcast it.</code>")


@Bot.on_message(filters.command("restart"))
async def restart_(client, message):
  if message.from_user.id not in Vars.ADMINS:
    return
  
  await message.reply_text("<code>....</code>")
  await (await create_subprocess_exec("python3", "update.py")).wait()
  execl(executable, executable, "-B", "main.py")




@Bot.on_message(filters.command("update"))
async def update_bot(client, message):
  if message.from_user.id not in Vars.ADMINS:
    return

  try:
      msg = await retry_on_flood(message.reply_text)("<b><blockquote>Pulling the latest updates and restarting the bot...</blockquote></b>")

      # Run git pull
      git_pull = subprocess.run(["git", "fetch"], capture_output=True, text=True)

      if git_pull.returncode == 0:
            await retry_on_flood(msg.edit_text)(f"<b><blockquote>Updates pulled successfully:\n\n{git_pull.stdout}</blockquote></b>")
      else:
            await retry_on_flood(msg.edit_text)(f"<b><blockquote>Failed to pull updates:\n\n{git_pull.stderr}</blockquote></b>")
            return

      await asyncio.sleep(3)

      await retry_on_flood(msg.edit_text)("<b><blockquote>✅ Bᴏᴛ ɪs ʀᴇsᴛᴀʀᴛɪɴɢ ɴᴏᴡ...</blockquote></b>")

  except Exception as e:
        await retry_on_flood(message.reply_text)(f"An error occurred: {e}")
        return

  finally:
    execl(executable, executable, "-B", "main.py")



def humanbytes(size):
  if not size:
    return ""
  units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
  size = float(size)
  i = 0
  while size >= 1024.0 and i < len(units) - 1:
    i += 1
    size /= 1024.0
  return "%.2f %s" % (size, units[i])


def get_process_stats():
  p = psutil.Process(os.getpid())
  
  mem_info = psutil.virtual_memory()
  try:
      cpu = p.cpu_percent(interval=0.5)
  except Exception:
      cpu = "N/A"
  try:
      mem_info = p.memory_info()
      rss = humanbytes(mem_info.rss)
      vms = humanbytes(mem_info.vms)
  except Exception:
      rss = vms = "N/A"
  
  return (
    f" ├ CPU: {cpu}%\n"
    f" ├ RAM (RSS): {rss}\n"
    f" └ RAM (VMS): {vms}\n"
    f" └ Cache: {humanbytes(get_cache())}"
  )


@Bot.on_message(filters.command('stats'))
async def show_stats(client, message):
  total_disk, used_disk, free_disk = shutil.disk_usage(".")
  total_disk_h = humanbytes(total_disk)
  used_disk_h = humanbytes(used_disk)
  free_disk_h = humanbytes(free_disk)
  disk_usage_percent = psutil.disk_usage('/').percent

  net_start = psutil.net_io_counters()
  time.sleep(2)
  net_end = psutil.net_io_counters()

  bytes_sent = net_end.bytes_sent - net_start.bytes_sent
  bytes_recv = net_end.bytes_recv - net_start.bytes_recv

  cpu_cores = os.cpu_count()
  cpu_usage = psutil.cpu_percent()

  ram = psutil.virtual_memory()
  ram_total = humanbytes(ram.total)
  ram_used = humanbytes(ram.used)
  ram_free = humanbytes(ram.available)
  ram_usage_percent = ram.percent

  try:
    uptime_seconds = time.time() - Vars.PING
    uptime = time.strftime("%Hh %Mm %Ss", time.gmtime(uptime_seconds))
  except Exception:
    uptime = "N/A"

  start_time = time.time()
  status_msg = await message.reply('📊 **Accessing System Details...**')
  end_time = time.time()
  time_taken_ms = int((end_time - start_time) * 1000)

  os_name = platform.system()
  os_version = platform.release()
  python_version = platform.python_version()

  response_text = f"""
🖥️ **System Statistics Dashboard**

💾 **Disk Storage**
├ Total:  `{total_disk_h}`
├ Used:  `{used_disk_h}` ({disk_usage_percent}%)
└ Free:  `{free_disk_h}`

🧠 **RAM (Memory)**
├ Total:  `{ram_total}`
├ Used:  `{ram_used}` ({ram_usage_percent}%)
├ Cache: `{humanbytes(ram.cached)}`
├ Buffers: `{humanbytes(ram.buffers)}`
└ Free:  `{ram_free}`

⚡ **CPU**
├ Cores:  `{cpu_cores}`
└ Usage:  `{cpu_usage}%`

🔌 **Bot Process**
{get_process_stats()}

🌐 **Network**
├ Upload Speed:  `{humanbytes(bytes_sent/2)}/s`
├ Download Speed:  `{humanbytes(bytes_recv/2)}/s`
└ Total I/O:  `{humanbytes(net_end.bytes_sent + net_end.bytes_recv)}`

📟 **System Info**
├ OS:  `{os_name}`
├ OS Version:  `{os_version}`
├ Pyrofork Version:  `{pyrogram.__version__}`
├ Python:  `{python_version}`
└ Uptime:  `{uptime}`

⏱️ **Performance**
└ Current Ping:  `{time_taken_ms:.3f} ms`

** Server **
├ County: `{client.county_info.get('country')}`
└ ISP: `{client.county_info.get('isp')}`
"""
  
  await retry_on_flood(message.reply_text)(response_text)
  await retry_on_flood(status_msg.delete)()


@Bot.on_message(filters.command("server"))
async def server_info(client, message):
  if message.from_user.id not in Vars.ADMINS:
    return
  
  await retry_on_flood(message.reply_text)(
    f"<b>Server Info:</b>\n\n"
    f"<b>Country:</b> {client.county_info.get('country')}\n"
    f"<b>ISP:</b> {client.county_info.get('isp')}\n"
    f"<b>IP:</b> {client.county_info.get('ip')} \n"
    f"<b>Region:</b> {client.county_info.get('regionName')}\n"
    f"<b>City:</b> {client.county_info.get('city')}\n"
    f"<b>Org:</b> {client.county_info.get('org')}\n"
  )


@Bot.on_message(filters.command("shell"))
async def shell(_, message):
  if message.from_user.id not in Vars.ADMINS:
    return
  
  cmd = message.text.split(maxsplit=1)
  if len(cmd) == 1:
    return await retry_on_flood(message.reply)("<code>No command to execute was given.</code>")

  cmd = cmd[1]
  proc = await asyncio.create_subprocess_shell(
    cmd, stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE
  )
  stdout, stderr = await proc.communicate()
  stdout = stdout.decode().strip()
  stderr = stderr.decode().strip()
  reply = ""
  if len(stdout) != 0:
    reply += f"<b>Stdout</b>\n<blockquote>{stdout}</blockquote>\n"
  if len(stderr) != 0:
    reply += f"<b>Stderr</b>\n<blockquote>{stderr}</blockquote>"

  if len(reply) > 3000:
    bio = BytesIO()
    bio.write(str(reply).encode('utf-8'))
    bio.seek(0)

    await retry_on_flood(message.reply_document)(bio, file_name="shell_output.txt")
    bio.close()

  elif len(reply) != 0:
    await retry_on_flood(message.reply)(reply)
  else:
    await retry_on_flood(message.reply)("No Reply")





@Bot.on_callback_query(filters.regex("^help$"))
@Bot.on_message(filters.command("help"))
async def help(client, message):
  try:
    if Vars.IS_PRIVATE and message.chat.id not in Vars.ADMINS:
      return await message.reply("<code>You cannot use me baby </code>")
  except Exception:
    pass

  try:
    await retry_on_flood(message.reply)(HELP_MSG)
  except Exception:
    await retry_on_flood(message.edit_message_text)(
      HELP_MSG,
      reply_markup=InlineKeyboardMarkup(help_button)
    )


@Bot.on_message(filters.command("sources") & filters.private)
async def sources_cmd(client, message):
  """Show interactive source management panel."""
  user_id = message.from_user.id
  from .settings import get_sources_panel  # noqa: PLC0415
  text, reply_markup = await get_sources_panel(user_id, page=1)
  await retry_on_flood(message.reply)(text, reply_markup=reply_markup)



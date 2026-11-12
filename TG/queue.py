# Code By @V_Sbotmaker (on Telegram)
from Tools.base import igrone_error
from bot import Bot, Vars, logger
from pyrogram import filters
from TG.storage import retry_on_flood, queue
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
import random
import asyncio

from pyrogram.types import BotCommand
from pyrogram.enums import ButtonStyle

botcommands = {
  "start": "Start the bot",
  "help": "Get help about the bot",
  "queue": "To Check Queue List",
  "user_setting": "To Change User Settings",
  "search": "To Search For A Manga",
  "subscribes": "To Check Your Subscribed Manga",
  
  "clean_tasks": "To Clean All Pending Tasks",
  "shell": "To Run Shell Commands",
  "stats": "To Get OS Stats Of Bot",
  "update": "To Update The Bot",
  "restart": "To Restart The Bot",
  "b": "To Broadcast Message To All Users",
  "pb": "To Broadcast Message To All Users With Pinning",
  "fd": "To Forward Message To All Users",
  "pfd": "To Forward Message To All Users With Pinning",
  "add_admin": "To Add New Admin",
  "export": "To Export Your Data",
  "import": "To Import Your Data",
  "my_plan": "To Check Your Premium Plan",
  "add_premium": "To Add Premium User",
  "del_premium": "To Delete Premium User",
  "premium": "To Check Premium Users",
  "server": "To Check Server Status",
  "sources": "To Check Supported Sources",
  "del_expired": "To Delete Expired Premium Users",
  "replace": "To Replace A Bot Message",
  "stop": "To Stop The Bot",
  "mybot": "To Check Your Personal Bot",
  "removebot": "To Remove Your Personal Bot",
  "del_sub": "To Delete Subscribed Manga",
  "update_ls": "To Check Last Updated Manga",
  "cls": "To Clear Subscribed Manga List",
  "update_subs": "To Update Subscribed Manga List",
  "cmds": "To Update Bot Commands",
}

@Bot.on_message(filters.command("cmds"))
async def set_bot_commands(client, message):
    if message.from_user.id not in Vars.ADMINS:
        return 
    
    bot_commands = [BotCommand(command, description) for command, description in botcommands.items()]
    await client.set_bot_commands(bot_commands)
    await retry_on_flood(message.reply_text)("<i> <b> Bot commands updated successfully! </b> </i>")


def get_queue_markup(user_error=None):
    button = [
        [
            InlineKeyboardButton(
                "⌜ 𝙲𝚕𝚎𝚊𝚗 𝚀𝚞𝚎𝚞𝚎 ⌟", 
                callback_data="clean_queue",
                style=ButtonStyle.SUCCESS,
            ),
            InlineKeyboardButton("⌜ 𝚂𝚞𝚋𝚜𝚌𝚛𝚒𝚋𝚎 ⌟", callback_data="isubs")
        ],
        [
            InlineKeyboardButton("▏ 𝗖𝗟𝗢𝗦𝗘 ▕", callback_data="kclose"),
            InlineKeyboardButton(" 𝗥𝗘𝗙𝗥𝗘𝗦𝗛 ⟳ ", callback_data="refresh_queue")
        ]
    ]
    if user_error:
        button.append([InlineKeyboardButton("♕ 𝙾𝚠𝚗𝚎𝚛 ♕", url="https://t.me/Wizard_Bots")])
    else:
        button.append([InlineKeyboardButton("♕ 𝙾𝚠𝚗𝚎𝚛 ♕", user_id=Vars.OWNER)])
    
    return InlineKeyboardMarkup(button)


async def get_queue_text(user_id):
    try:
        total_tasks = queue.qsize()
        total_users = queue.get_count()

        # Flatten all ongoing tasks from the new list-based structure
        ongoing_tasks_flat = [
            task
            for tasks_list in queue.ongoing_tasks.values()
            for task in tasks_list
        ]

        reply_txt = (
            f"<blockquote><b>📌 Queue Status (Total: {total_tasks} chapters & {total_users} Users)</b></blockquote>\n\n"
            "**👤 Your queue:**"
        )

        user_count = queue.get_count(user_id)
        uid_str = str(user_id)

        if user_count != 0:
            reply_txt += f"""<blockquote expandable>=> <i>Total Chapters: {user_count}</i>\n"""

            # Check if user has ongoing tasks
            user_ongoing = queue.ongoing_tasks.get(uid_str, [])
            if user_ongoing:
                for task in user_ongoing:
                    reply_txt += f"=> <i>{task.manga_title} - {task.episode_number}</i>\n"
                    reply_txt += f"=> <i>{task.status}...</i>\n"
            else:
                # Show first pending task from storage (read-only, no claim)
                first_pending = next(
                    (t for t, _ in queue.storage_data.values()
                     if str(t.user_id) == uid_str),
                    None
                )
                if first_pending:
                    reply_txt += f"=> <i>{first_pending.manga_title} - {first_pending.episode_number}</i>\n"
                    reply_txt += "=> <i>Waiting...</i>\n"
                else:
                    reply_txt += "=> <i>In queue...</i>\n"
            reply_txt += "</blockquote>\n"
        else:
            reply_txt += "\n=> <i>No chapters in your queue.</i>\n"

        # Global processing section
        reply_txt += "\n**🚦 Now Processing:**\n"
        if ongoing_tasks_flat:
            reply_txt += "<blockquote expandable>"
            # Group by user for display
            seen_users: dict = {}
            for task in ongoing_tasks_flat:
                uid = int(task.user_id)
                seen_users.setdefault(uid, []).append(task)

            for i, (uid, tasks_list) in enumerate(seen_users.items(), 1):
                try:
                    user_query = await Bot.get_users(uid)
                    mention = user_query.mention()
                except Exception as e:
                    logger.warning(f"Failed to get user info for {uid}: {e}")
                    mention = f"User[{uid}]"

                worker_count = len(tasks_list)
                reply_txt += f"{i}. {mention} ({worker_count} worker{'s' if worker_count > 1 else ''})\n"
            reply_txt += "</blockquote>\n"
        else:
            reply_txt += "=> <i>No active processing tasks.</i>\n\n"

        reply_txt += "<b>=> <i>Other chapters are in the waiting line.</i></b>"
        return reply_txt

    except Exception as e:
        logger.exception(f"Error generating queue text: {e}")
        return "❌ Error generating queue information."


@Bot.on_message(filters.command("queue"))
async def queue_msg_handler(client, message):
    if Vars.IS_PRIVATE and message.chat.id not in Vars.ADMINS:
        return await message.reply("<code>You cannot use this command.</code>")

    try:
        await retry_on_flood(message.reply_text)(
            await get_queue_text(message.from_user.id),
            reply_markup=get_queue_markup()
        )
    except Exception:
        try:
            await retry_on_flood(message.reply_text)(
                await get_queue_text(message.from_user.id),
                reply_markup=get_queue_markup(True)
            )
        except Exception as e:
            logger.error(f"Queue command error: {e}")
            await message.reply("❌ Failed to fetch queue information.")



@Bot.on_callback_query(filters.regex("^refresh_queue$"))
async def queue_refresh_handler(_, query):
    """Refresh queue information"""
    try:
        rand_photo = random.choice(Vars.PICS)
        try:
            await retry_on_flood(query.edit_message_media)(
                InputMediaPhoto(rand_photo, await get_queue_text(query.from_user.id)),
                reply_markup=get_queue_markup()
            )
        except Exception:
            await retry_on_flood(query.edit_message_media)(
                InputMediaPhoto(rand_photo, await get_queue_text(query.from_user.id)),
                reply_markup=get_queue_markup(True)
            )
            
        await igrone_error(query.answer)("✅ Queue refreshed!")
    except Exception as e:
        logger.error(f"Queue refresh error: {e}")
        await igrone_error(query.answer)("❌ Failed to refresh queue.", show_alert=True)


@Bot.on_callback_query(filters.regex("^clean_queue$"))
async def clean_queue_handler(_, query):
    """Clean user's queue"""
    try:
        user_id = query.from_user.id
        if queue.get_count(user_id):
            numb = await queue.delete_tasks(user_id)
            await retry_on_flood(query.answer)(f"✅ All your tasks deleted: {numb}")

            await asyncio.sleep(1)
            rand_photo = random.choice(Vars.PICS)
            await retry_on_flood(query.edit_message_media)(
                InputMediaPhoto(
                    rand_photo,
                    caption=await get_queue_text(user_id)
                ),
                reply_markup=get_queue_markup(True)
            )
        else:
            await retry_on_flood(query.answer)("ℹ️ There are no pending tasks in your queue.")
    except Exception as e:
        logger.error(f"Clean queue error: {e}")
        await query.answer("❌ Failed to clean queue.", show_alert=True)

# Code By @V_Sbotmaker (on Telegram)
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from bot import Bot, Vars, logger, TimeoutError
from Tools.db import database
from .storage import igrone_error, retry_on_flood, translation as tr
import random
from pyrogram.enums import ButtonStyle


# ─── Constants ───────────────────────────────────────────────────────────────

users_txt = """

<b><blockquote expandable>➥ File Name: <code>{file_name}</code><code>[{len}]</code>
➥ Caption: <code>{caption}</code>
➥ Thumbnail: <code>{thumb}</code>
➥ File Type: <code>{type}</code>
➥ PDF Password: <code>{password}</code>
➥ Megre Size: <code>{megre}</code>
➥ Regex/Zfill: <code>{regex}</code>
➥ Banner 1: <code>{banner1}</code>
➥ Banner 2: <code>{banner2}</code>
➥ Dump Channel: <code>{dump}</code>
➥ Compression Quality: <code>{compress}</code>
➥ HyperLink: <code>{hyper}</code>"""

auto_user_txt = """
➥ Update Channel : <code>{update_c}</code>
➥ Update Button: <code>{update_b}</code>
➥ Update Text: <code>{update_t}</code>
➥ Update Sticker: <code>{update_s}</code>
➥ Channel Sticker: <code>{target_s}</code></blockquote></b>"""

users_txt_close = "</blockquote></b>"

info_data_text = {
    "caption": {
        "type": "Caption",
        "text": """
<b>📐 Send Caption 📐 

<u>Note:</u> <blockquote>Use HTML Tags For Bold, Italic,etc</blockquote>

<u>Params:</u>
➥ <code>{manga_title}</code>: Manga Name
➥ <code>{chapter_num}</code>: Chapter Number
➥ <code>{file_name}</code>: File Name</b>

➥ /cancel: To Cancel The Process""",
        "caption": """
<b><blockquote>Caption</blockquote>

<blockquote expandable>Format:
➥ <code>{manga_title}</code>: Manga Name
➥ <code>{chapter_num}</code>: Chapter Number
➥ <code>{file_name}</code>: File Name</blockquote>

<blockquote>➥ Your Value: <code>{value}</code></blockquote></b>"""
    },

    "dump": {
        "type": "Dump Channel",
        "text": """
<b>📐 Send Dump Channel 📐 

➥ /cancel: To Cancel The Process

<u>Note:</u> <blockquote>You Can Send Username(without @) or Channel Id or Forward Message from Channel.. </blockquote></b>"""
    },

    "megre": {
        "type": "Megre Size",

        "text": """<b>📐 Send Megre Size 📐 

➥ /cancel: To Cancel The Process

<u>Note:</u> <blockquote>It's Number For Megre. i.e 2, 3 ,4 ,5,etc </blockquote></b>"""
    },

    "password": {
        "type": "Password",
        "text": "<b>📐 Send Password 📐 \n\n➥ /cancel: To Cancel Process \n\n<u>Note:</u> <blockquote>It's Password For PDF.</blockquote></b>"
    },

    "hyper": {
        "type": "HyperLink",
        "text": "<b>📐 Send HyperLink 📐 \n\n➥ /cancel: To cancel process \n\n<u>Note:</u> <blockquote>It's HyperLink For PDF.</blockquote></b>"
    },

    "update_c": {
        "type": "Update Channel",
        "text": "<b>📐 Send Update Channel 📐 \n\n➥ /cancel: To cancel process\n\n<u>Note:</u> <blockquote>You Can Send Username(without @) or Channel Id or Forward Message from Channel.. </blockquote></b>"
    },

    "update_t": {
        "type": "Update Text",
        "text": """<b>📐 Send Update Text 📐 

<u>Note:</u> <blockquote>It's Update Text For Update Channel. </blockquote>

<u>Params:</u>
➥ <code>{manga_title}</code>: Manga Name
➥ <code>{chapter_num}</code>: Chapter Number
➥ <code>{channel_title}</code>: Channel Title
➥ <code>{channel_link}</code>: To Redirect to Channel
➥ <code>{read_link}</code>: To Redirect to Read Link

<u>* Donot forget to use <: from and >: for redirecting to links, See Example Below *</u>

<u>Example</u>
<code>{channel_title}

➥ < Cʜᴀᴘᴛᴇʀ {chapter_num} >{read_link} Uᴘᴅᴀᴛᴇᴅ
➥ < Rᴇᴀᴅ Nᴏᴡ >{channel_link} </code></b>""",
        "caption": """
<b><blockquote>➥ Update Text</blockquote>

<blockquote expandable><u>Params:</u>
➥ <code>{manga_title}</code>: Manga Name
➥ <code>{chapter_num}</code>: Chapter Number
➥ <code>{channel_title}</code>: Channel Title
➥ <code>{channel_link}</code>: To Redirect to Channel
➥ <code>{read_link}</code>: To Redirect to Read Link

<u>* Donot forget to use <: from and >: for redirecting to links, See Example Below *</u></blockquote>

<blockquote>➥ Your Value: <code>{value}</code></blockquote></b>
"""
    },

    "update_s": {
        "type": "Update Sticker",
        "text": "<b>📐 Send Update Sticker 📐 \n<u>Note:</u> <blockquote>It's Update Sticker For Update Channel.</blockquote></b>"
    },

    "target_s": {
        "type": "Channel Sticker",
        "text": "<b>📐 Send Target Channel Sticker 📐 \n<u>Note:</u> <blockquote>It's Upload Sticker when Updating in Target channel. You Can Send Username(without @) or Channel Id or Forward Message from Channel.. </blockquote></b>"
    },

    "file_name": {
        "type": "File Name",
        "text": "<b>📐 Send File Name 📐 \n\n<u><i>Params:</u></i>\n➥<code>{manga_title}</code>: Manga Name \n➥ <code>{chapter_num}</code>: Chapter Number\n\n➥/cancel: To cancel process</b>",
        "caption": """
<b><blockquote>➥ File Name </blockquote>

<blockquote expandable><u><i>Params:</u>
➥ <code>{manga_title}</code>: Manga Name 
➥ <code>{chapter_num}</code>: Chapter Number</blockquote>

<blockquote>➥ Your File Name: <code>{value}</code>
➥ Your File Name Len: <code>{flen}</code></blockquote></b>"""
    },

    "update_b": {
        "type": "Update Button",
        "text": """
<b>➥ 📐 Send Update Button 📐

➥ <u>Note:</u> <blockquote>It's Update Button For Update Channel.</blockquote>

➥ <u>Params:</u>
➥ manga_title: Manga Name
➥ chapter_num : Chapter Number
➥ channel_title: Channel Title
➥ channel_link: To Redirect to Channel
➥ read_link: To Redirect to Read Link
➥ channel_req_link: To Redirect to Channel with request
➥  - : To Seperate Button Text and Link
➥  && / |: To Seperate Buttons
➥ #r: Red Color
➥ #b: Blue Color
➥ #g: Green Color

➥ <u>Example</u>

<pre>#r Join Channel {channel_title} - {channel_link} | #b {chapter_num} - {read_link}
Next Line Button Text - http://www.example3.com/
Next Line Another Button Text - http://www.example3.com/</pre>

➥ Format:- <code>Text - Url </code>
➥ Do not add any text in the URL part. If you do, the bot will ignore it.
➥ /cancel :- To Cancel Process </b>""",
        
        "caption": """
<b><blockquote>➥ Update Button</blockquote>

<blockquote expandable><u>Params:</u>
➥ <code>{manga_title}</code>: Manga Name
➥ <code>{chapter_num}</code>: Chapter Number
➥ <code>{channel_title}</code>: Channel Title
➥ <code>{channel_link}</code>: To Redirect to Channel
➥ <code>{read_link}</code>: To Redirect to Read Link
➥ <code> && </code>: To Seperate Buttons
➥ <code> - </code>: To Seperate Button Text and Link</blockquote>
➥ #r: Red Color
➥ #b: Blue Color
➥ #g: Green Color

<blockquote>➥ Your Value: <code>{value}</code></blockquote></b>"""
    }
}

simple_caption_txt_format = "<blockquote expandable><b>➥ {type}\n\n➥ Your Value: {value}</b></blockquote>"

# ─── Shared keyboard builders ─────────────────────────────────────────────────

BACK_CLOSE_ROW = [
    InlineKeyboardButton(tr(" ⇦ Back "), callback_data="mus"),
    InlineKeyboardButton(tr(" ✵ Close ✵ "), callback_data="close"),
]

HOME_CLOSE_ROW = [
    InlineKeyboardButton(tr("✧ Home ✧"), callback_data="home"),
    InlineKeyboardButton(tr("✵ Close ✵"), callback_data="close"),
]


def _set_delete_row(type_key: str) -> list:
    return [
        InlineKeyboardButton(tr(" Set / Change "), callback_data=f"sset_{type_key}"),
        InlineKeyboardButton(tr(" Delete "), callback_data=f"sdelete_{type_key}"),
    ]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _decode_base64_image(data: str):
    """Decode a base64 image string into a BytesIO object."""
    import base64
    from io import BytesIO

    b64 = data.split(",", 1)[1] if data.startswith("data:") else data
    img = BytesIO(base64.b64decode(b64))
    img.name = "image.jpg"
    return img


def _is_base64_image(s: str) -> bool:
    return s.startswith("data:image") or s.startswith("/9j") or s.startswith("iVBOR")


def _resolve_media(value: str | None, fallback_pics: tuple):
    """Return a Telegram-compatible media source, falling back to a random pic."""
    if value and isinstance(value, str) and _is_base64_image(value):
        return _decode_base64_image(value)

    return value or random.choice(fallback_pics)


def _build_caption_for_type(type_key: str, usettings: dict) -> str:
    """Build the info caption for a given settings key."""
    caption_txt = info_data_text.get(type_key, {}).get("caption") or simple_caption_txt_format
    flen = usettings.get("file_name_len", "None")
    value = usettings.get(type_key, "None")

    if type_key in ("update_s", "target_s"):
        value = "True" if value else "None"

    caption_txt = (
        caption_txt
        .replace("{type}", info_data_text.get(type_key, {}).get("type", "Unknown"))
        .replace("{value}", str(value))
        .replace("{flen}", str(flen))
    )

    if len(caption_txt) > 1024:
        caption_txt = (
            simple_caption_txt_format
            .replace("{type}", info_data_text.get(type_key, {}).get("type", "Unknown"))
            .replace("{value}", str(value))
        )

    return caption_txt


# ─── Main settings text builder ───────────────────────────────────────────────

caption_sample_text = """<b><blockquote>➥ User Setting Panel</blockquote>

<blockquote expandable>➥ ID: <code>{user_id}</code>
➥ Full Name: <code>{full_name}</code>
➥ DC ID: <code>{dc_id}</code></blockquote></b>"""


async def get_user_txt(user_id: int | str) -> str:
    user_id = str(user_id)
    uts = await database.get_settings(user_id)

    def _thumb_label(v):
        if not v:
            return v
        if v == "constant":
            return "Constant"
        return v if v.startswith("http") else "True"

    def _banner_label(v):
        if not v:
            return v
        return v if v.startswith("http") else "True"

    thumb   = _thumb_label(uts.get("thumb"))
    banner1 = _banner_label(uts.get("banner1"))
    banner2 = _banner_label(uts.get("banner2"))

    update_s = "True" if uts.get("update_s") else "False"
    target_s = "True" if uts.get("target_s") else "False"

    format_txt = users_txt + (auto_user_txt if Vars.AUTO_F else users_txt_close)

    return format_txt.format(
        id=user_id,
        file_name=uts.get("file_name", "None"),
        caption=uts.get("caption", "None"),
        thumb=thumb,
        banner1=banner1,
        banner2=banner2,
        dump=uts.get("dump", "None"),
        type=uts.get("type", "None"),
        megre=uts.get("megre", "None"),
        regex=uts.get("regex", "None"),
        len=uts.get("file_name_len", "None"),
        password=uts.get("password", "None"),
        compress=uts.get("compress", "None"),
        hyper=uts.get("hyper", "None"),
        update_c=uts.get("update_c", "None"),
        update_t=uts.get("update_t", "None"),
        update_s=update_s,
        target_s=target_s,
        update_b=uts.get("update_b", "None"),
    )


# ─── Settings panel ───────────────────────────────────────────────────────────

def _build_main_buttons() -> list:
    button = [
        [
            InlineKeyboardButton(tr(" Banner "), callback_data="ubn"),
            InlineKeyboardButton(tr(" Caption "), callback_data="sinfo_caption"),
        ],
        [
            InlineKeyboardButton(tr(" Channel Stickers "), callback_data="sinfo_target_s"),
            InlineKeyboardButton(tr(" Comprass "), callback_data="u_compress"),
        ],
        [
            InlineKeyboardButton(tr(" File Name "), callback_data="sinfo_flen"),
            InlineKeyboardButton(tr(" File Type"), callback_data="u_file_type"),
        ],
        [
            InlineKeyboardButton(tr(" HyperLink "), callback_data="sinfo_hyper"),
            InlineKeyboardButton(tr(" Megre Size "), callback_data="sinfo_megre"),
        ],
        [
            InlineKeyboardButton(tr(" Password "), callback_data="sinfo_password"),
            InlineKeyboardButton(tr(" Regex "), callback_data="uregex"),
        ],
        [
            InlineKeyboardButton(tr(" Dump Channel "), callback_data="sinfo_dump"),
        ],
        [
            InlineKeyboardButton(tr(" Thumbnail "), callback_data="uth"),
            InlineKeyboardButton(tr(" Update Channel "), callback_data="sinfo_update_c"),
        ],
        [
            InlineKeyboardButton(tr(" 🌐 Manage Sources "), callback_data="sources_panel:1", style=ButtonStyle.PRIMARY),
        ],
    ]

    if Vars.AUTO_F:
        button.insert(0, [
            InlineKeyboardButton(
                tr(" Auto Update Channels "), 
                callback_data="auto_channel",
                style=ButtonStyle.PRIMARY
            )
        ])
        
        button.insert(4, [
            InlineKeyboardButton(
                tr(" Auto Upload Channels "), 
                callback_data="target_channel",
                style=ButtonStyle.PRIMARY 
            )
        ])
        
        button.extend([
            [
                InlineKeyboardButton(tr(" Update Text "), callback_data="sinfo_update_t"),
                InlineKeyboardButton(tr(" Update Sticker "), callback_data="sinfo_update_s"),
            ],
            [InlineKeyboardButton(tr(" Update Button "), callback_data="sinfo_update_b")],
            [
                InlineKeyboardButton(" 𝘉𝘦𝘧𝘰𝘳𝘦 𝘗𝘰𝘴𝘵 ", callback_data="before_post"),
                InlineKeyboardButton(" 𝘈𝘧𝘵𝘦𝘳 𝘗𝘰𝘴𝘵 ", callback_data="after_post"),
            ],
        ])

    button.append(HOME_CLOSE_ROW)
    return button


async def main_settings(_, message_query, user_id: int | str):
    user_id_str = str(user_id)
    await database.ensure_user(user_id_str)

    settings = await database.get_settings(user_id_str)
    thumbnali = settings.get("thumb")

    try:
        user_info = await Bot.get_users(user_id)
        if isinstance(user_info, list):
            user_info = None
    except Exception:
        user_info = None

    caption_txt = caption_sample_text.format(
        user_id=user_id_str,
        full_name=user_info.first_name if user_info else "None",
        dc_id=user_info.dc_id if user_info else "None",
    )

    user_panel_text = await get_user_txt(user_id_str)


    combined = caption_txt + user_panel_text
    if len(combined) <= 1024:
        caption_txt = combined

    elif len(user_panel_text) <= 1024:
        caption_txt = user_panel_text

    button = _build_main_buttons()

    
    if not thumbnali or thumbnali == "constant":
        photo = random.choice(Vars.PICS)
    
    else:
        photo = _resolve_media(thumbnali, Vars.PICS)

    try:
        await retry_on_flood(message_query.edit_media)(
            InputMediaPhoto(photo, caption=caption_txt),
            reply_markup=InlineKeyboardMarkup(button),
        )
    except Exception:
        await retry_on_flood(message_query.edit_media)(
            InputMediaPhoto(Vars.PICS[0], caption=caption_txt),
            reply_markup=InlineKeyboardMarkup(button),
        )


# ─── Command handler ──────────────────────────────────────────────────────────

@Bot.on_message(filters.command(["us", "user_setting"]))
async def userxsettings(client, message):
    if Vars.IS_PRIVATE and message.chat.id not in Vars.ADMINS:
        return await message.reply("<code>You cannot use me baby </code>")

    sts = await retry_on_flood(message.reply)("<code>Processing...</code>")
    await database.ensure_user(message.from_user.id)

    try:
        await main_settings(client, sts, message.from_user.id)
    except Exception as err:
        logger.exception(err)
        await retry_on_flood(sts.edit)(str(err))


# ─── Callback: main user panel ────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex("^mus$"))
async def main_user_panel(_, query):
    await igrone_error(query.answer)()
    await database.ensure_user(query.from_user.id)
    await main_settings(_, query.message, query.from_user.id)


# ─── Callback: info panel for each setting ────────────────────────────────────

@Bot.on_callback_query(filters.regex("^sinfo"))
async def user_settings(_, query):
    type_key = query.data.split("_", 1)[-1]
    user_id = str(query.from_user.id)
    await database.ensure_user(user_id)

    usettings = await database.get_settings(user_id)


    if type_key in ("flen", "file_name_len"):
        type_key = "file_name"

    if type_key in ("update_s", "target_s"):
        value = usettings.get(type_key)
        sticker_id = value  # keep original file_id for reply

        button = [_set_delete_row(type_key), BACK_CLOSE_ROW]

        if sticker_id:
            await retry_on_flood(query.message.reply_sticker)(
                sticker_id,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✵ 𝘊𝘭𝘰𝘴𝘦 ✵", callback_data="close")]
                ]),
            )

    elif type_key == "file_name":
        button = [
            _set_delete_row("file_name"),
            [
                InlineKeyboardButton(tr(" Change Len "), callback_data="sset_file_name_len"),
                InlineKeyboardButton(tr(" Delete "), callback_data="sdelete_file_name_len"),
            ],
            BACK_CLOSE_ROW,
        ]

    else:
        button = [_set_delete_row(type_key), BACK_CLOSE_ROW]

    caption_txt = _build_caption_for_type(type_key, usettings)

    await igrone_error(query.answer)()
    try:
        await retry_on_flood(query.edit_message_media)(
            InputMediaPhoto(random.choice(Vars.PICS), caption_txt),
            reply_markup=InlineKeyboardMarkup(button),
        )
    except Exception:
        await retry_on_flood(query.edit_message_reply_markup)(InlineKeyboardMarkup(button))


# ─── Callback: set a setting value ────────────────────────────────────────────

_FORWARD_TYPES = {"dump", "update_c", "file_name_len"}
_STICKER_TYPES = {"update_s", "target_s"}


@Bot.on_callback_query(filters.regex("^sset"))
async def user_settings_set(_, query):
    type_key = query.data.removeprefix("sset_")
    user_id = str(query.from_user.id)
    await database.ensure_user(user_id)

    try:
        if type_key == "file_name_len":
            caption_txt = "<b>📐 Send File Name Len 📐\n Example: 15, 20, 50</b>"
        else:
            caption_txt = info_data_text.get(type_key, {}).get(
                "text",
                "<i> ➥ Text Not Found !, Report to Admins and send /cancel </i>",
            )

        await retry_on_flood(query.edit_message_caption)(caption_txt)

        call_ = await _.listen(
            user_id=int(user_id),
            timeout=80,
            filters=filters.text | filters.forwarded | filters.sticker,
        )

        if call_.text == "/cancel":
            await igrone_error(query.answer)("Sucessfully Cancelled")

        elif type_key in _FORWARD_TYPES:
            if call_.forward_from_chat:
                await database.set_value(user_id, type_key, call_.forward_from_chat.id)

            elif call_.text:

                try:
                    value = int(call_.text)
                except (ValueError, TypeError):
                    value = call_.text
                await database.set_value(user_id, type_key, value)

        elif type_key in _STICKER_TYPES:
            if call_.sticker:
                await database.set_value(user_id, type_key, call_.sticker.file_id)
                await igrone_error(query.answer)(tr("🎮 Sucessfully Added 🎮"))
            else:
                await retry_on_flood(query.message.reply_text)(
                    "📐 ᴛʜɪs ɪs ɴᴏᴛ ᴀ ᴠᴀʟɪᴅ sᴛɪᴄᴋᴇʀ 📐"
                )

        else:
            await database.set_value(user_id, type_key, call_.text)

        await igrone_error(call_.delete)()

    except TimeoutError:
        await igrone_error(query.answer)("📐 ᴛɪᴍᴇᴏᴜᴛ 📐")
    except Exception as err:
        await igrone_error(query.answer)(f"📐 {err} 📐")


    await igrone_error(query.answer)()
    query.data = f"sinfo_{type_key}"
    await user_settings(_, query)


# ─── Callback: delete a setting value ────────────────────────────────────────

@Bot.on_callback_query(filters.regex("^sdelete"))
async def user_settings_delete(_, query):
    type_key = query.data.removeprefix("sdelete_")
    user_id = str(query.from_user.id)
    await database.ensure_user(user_id)

    usettings = await database.get_settings(user_id)

    if usettings.get(type_key) is not None:
        await database.delete_value(user_id, type_key)
        await retry_on_flood(query.answer)("Sucessfully Deleted")
        query.data = f"sinfo_{type_key}"
        await user_settings(_, query)
    else:
        await retry_on_flood(query.answer)(
            "📐 𝒀𝒐𝒖 𝒉𝒂𝒔 𝒏𝒐𝒕 𝑺𝒆𝒕 𝑰𝒕 ! 📐", show_alert=True
        )


# ─── Callback: thumbnail handler ─────────────────────────────────────────────

def _thumb_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(tr(" Change "), callback_data="uth_change"),
            InlineKeyboardButton(tr(" Delete "), callback_data="uth_delete"),
        ],
        [
            InlineKeyboardButton(tr(" Constant "), callback_data="uth_constant", style=ButtonStyle.SUCCESS)
        ],
        [
            InlineKeyboardButton(tr(" ⇦ Back "), callback_data="mus"),
            InlineKeyboardButton(tr(" ✵ Close ✵ "), callback_data="close"),
        ],
    ])


@Bot.on_callback_query(filters.regex("^uth"))
async def thumb_handler(_, query):
    user_id = str(query.from_user.id)
    await database.ensure_user(user_id)

    usettings = await database.get_settings(user_id)
    thumbnali = usettings.get("thumb")

    if query.data == "uth_constant":
        await database.set_value(user_id, "thumb", "constant")
        await retry_on_flood(query.answer)("🎮 Sucessfully Added 🎮")

    elif query.data == "uth_change":
        await retry_on_flood(query.edit_message_caption)(
            "<b>📐 Send Thumbnail 📐\n<u>Note:</u> <blockquote>Links, Images, or Base64 (data:image/...)</blockquote></b>"
        )
        try:
            c = await _.listen(user_id=int(user_id), timeout=60)
            v = c.photo or c.document or None

            if v:
                t = v.file_id
                await database.set_value(user_id, "thumb", t)
            else:
                t = c.text
                if (
                    t.startswith("http")
                    or t.startswith("data:image")
                    or _is_base64_image(t)
                ):
                    await database.set_value(user_id, "thumb", t)
                else:
                    await igrone_error(query.answer)("📐 Invalid 📐")
                    await igrone_error(query.message.reply)(f"📐 Invalid 📐\n\n<code>{t}</code>")

            await igrone_error(c.delete)()
            await igrone_error(query.answer)("🎮 Added 🎮")

        except TimeoutError:
            await igrone_error(query.answer)("📐 Timeout 📐", True)
        except Exception as e:
            await igrone_error(query.answer)(f"📐 {e} 📐", True)

    elif query.data == "uth_delete":
        if thumbnali:
            await database.delete_value(user_id, "thumb")
        else:
            await igrone_error(query.answer)("📐 Not Set 📐")


    await igrone_error(query.answer)()
    usettings = await database.get_settings(user_id)
    t = usettings.get("thumb")

    tt = "Constant" if t and str(t).lower() == "constant" else ("True" if t else "None")
    txt = (
        simple_caption_txt_format.replace("{type}", "Thumbnail").replace("{value}", tt)
        + "\n\n<blockquote><b>➥ Constant:- MANGA POSTER AS THUMB</b></blockquote>"
    )

    photo = _resolve_media(
        None if (not t or str(t).lower() == "constant") else t,
        Vars.PICS,
    )

    try:
        await retry_on_flood(query.edit_message_media)(
            InputMediaPhoto(photo, txt), _thumb_markup()
        )
    except Exception:
        await retry_on_flood(query.edit_message_media)(
            InputMediaPhoto(random.choice(Vars.PICS), txt), _thumb_markup()
        )


# ─── Callback: banner handler ─────────────────────────────────────────────────

def _banner_markup(b1t: str, b2t: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(" 𝘚𝘦𝘵 / 𝘊𝘩𝘢𝘯𝘨𝘦 - 1 ", callback_data="ubn_set1"),
            InlineKeyboardButton(" 𝘋𝘦𝘭𝘦𝘵𝘦 - 𝟷 ", callback_data="ubn_delete1"),
        ],
        [InlineKeyboardButton(" 𝘚𝘩𝘰ᴡ 𝘉𝘢𝘯𝘯𝘦𝘳 - 1 ", callback_data="ubn_show1")],
        [
            InlineKeyboardButton(" 𝘚𝘦𝘵 / 𝘊𝘩𝘢𝘯𝘨𝘦 - 2 ", callback_data="ubn_set2"),
            InlineKeyboardButton("𝘋𝘦𝘭𝘦𝘵𝘦 - 𝟸", callback_data="ubn_delete2"),
        ],
        [InlineKeyboardButton(" 𝘚𝘩𝘰ᴡ 𝘉𝘢𝘯𝘯𝘦𝘳 - 2 ", callback_data="ubn_show2")],
        [
            InlineKeyboardButton(" ⇦ 𝘉𝘢𝘤𝘬 ", callback_data="mus"),
            InlineKeyboardButton(" ✵ 𝘊𝘭𝘰𝘴𝘦 ✵ ", callback_data="close"),
        ],
    ])


@Bot.on_callback_query(filters.regex("^ubn"))
async def banner_handler(_, query):
    user_id = str(query.from_user.id)
    await database.ensure_user(user_id)

    uts = await database.get_settings(user_id)
    banner1 = uts.get("banner1")
    banner2 = uts.get("banner2")

    if query.data.startswith("ubn_set"):
        await retry_on_flood(query.edit_message_media)(
            InputMediaPhoto(
                random.choice(Vars.PICS),
                "<b>📐 Send Banner 📐\n<u>Note:</u> <blockquote>URL (http...), Image, or Base64 (data:image/...)</blockquote></b>",
            )
        )
        try:
            c = await _.listen(user_id=int(user_id), timeout=60)
            v = c.photo or c.document or None
            if v:
                s = c.photo.file_id if c.photo else c.document.file_id
            else:
                s = c.text
                if not (s.startswith("http") or _is_base64_image(s)):
                    await retry_on_flood(query.answer)("📐 Invalid 📐")
                    return

            key = "banner1" if query.data == "ubn_set1" else "banner2"
            await database.set_value(user_id, key, s)
            await igrone_error(c.delete)()
            await igrone_error(query.answer)("🎬 Added 🎬")

        except TimeoutError:
            await igrone_error(query.answer)("📐 Timeout 📐", True)
        except Exception as e:
            await igrone_error(query.answer)(f"📐 {e} 📐", True)

    elif query.data in ("ubn_delete1", "ubn_delete2"):
        key = "banner1" if query.data == "ubn_delete1" else "banner2"
        current = banner1 if key == "banner1" else banner2
        if current:
            await database.delete_value(user_id, key)
        else:
            return await igrone_error(query.answer)("📐 Not Set 📐", True)

    elif query.data.startswith("ubn_show"):
        target = banner1 if query.data == "ubn_show1" else banner2 if query.data == "ubn_show2" else None
        if not target:
            return await igrone_error(query.answer)("📐 Not Set 📐", True)

        try:
            photo = _resolve_media(target, Vars.PICS)
            await retry_on_flood(query.message.reply_photo)(
                photo,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✵ 𝘊𝘭𝘰𝘴𝘦 ✵", callback_data="close")]
                ]),
            )
            await igrone_error(query.answer)()
        except Exception:
            await igrone_error(query.answer)("📐 Error 📐", True)
        return


    uts = await database.get_settings(user_id)
    b1 = uts.get("banner1")
    b2 = uts.get("banner2")
    b1t = "True" if b1 else "None"
    b2t = "True" if b2 else "None"

    bs = _resolve_media(b1 or b2, Vars.PICS)
    cap = f"<b><blockquote>Banner Setting</blockquote>\n\n<blockquote>➥ First: {b1t}\n➥ Last: {b2t}</blockquote></b>"

    await igrone_error(query.answer)()
    try:
        await retry_on_flood(query.edit_message_media)(
            InputMediaPhoto(bs, cap), _banner_markup(b1t, b2t)
        )
    except Exception:
        await retry_on_flood(query.edit_message_media)(
            InputMediaPhoto(random.choice(Vars.PICS), cap), _banner_markup(b1t, b2t)
        )


# ─── Callback: file type toggle ───────────────────────────────────────────────

def _build_file_type_buttons(type_list: list) -> InlineKeyboardMarkup:
    pdf_btn = (
        InlineKeyboardButton("📙 PDF 📙", callback_data="u_file_type_pdf")
        if "PDF" in type_list
        else InlineKeyboardButton("❗PDF ❗", callback_data="u_file_type_pdf")
    )

    cbz_btn = (
        InlineKeyboardButton("📂 CBZ 📂", callback_data="u_file_type_cbz")
        if "CBZ" in type_list
        else InlineKeyboardButton("❗CBZ ❗", callback_data="u_file_type_cbz")
    )

    return InlineKeyboardMarkup([
        [pdf_btn, cbz_btn],
        BACK_CLOSE_ROW,
    ])


@Bot.on_callback_query(filters.regex("^u_file_type"))
async def type_handler(_, query):
    user_id = str(query.from_user.id)
    await database.ensure_user(user_id)

    uts = await database.get_settings(user_id)
    type_list = list(uts.get("type") or [])

    if query.data == "u_file_type_pdf":
        if "PDF" in type_list:
            type_list.remove("PDF")
        else:
            type_list.append("PDF")
    elif query.data == "u_file_type_cbz":
        if "CBZ" in type_list:
            type_list.remove("CBZ")
        else:
            type_list.append("CBZ")

    await database.set_value(user_id, "type", type_list)

    caption_text = (
        simple_caption_txt_format
        .replace("{type}", "File Type")
        .replace("{value}", str(type_list))
    )

    await retry_on_flood(query.edit_message_media)(
        media=InputMediaPhoto(random.choice(Vars.PICS), caption_text),
        reply_markup=_build_file_type_buttons(type_list),
    )
    await igrone_error(query.answer)()


# ─── Callback: regex / zfill ─────────────────────────────────────────────────

@Bot.on_callback_query(filters.regex("^uregex"))
async def regex_handler(_, query):
    user_id = str(query.from_user.id)
    await database.ensure_user(user_id)

    uts = await database.get_settings(user_id)
    regex = uts.get("regex")

    if query.data.startswith("uregex_set_"):
        regex = query.data.split("_")[-1]
        await database.set_value(user_id, "regex", regex)

    elif query.data == "uregex_delete":
        if regex:
            regex = None
            await database.set_value(user_id, "regex", None)
        else:
            await retry_on_flood(query.answer)("📐 𝒀𝒐𝒖 𝒉𝒂𝒔 𝒏𝒐𝒕 𝑺𝒆𝒕 𝑰𝒕 ! 📐")


    regex = (await database.get_settings(user_id)).get("regex")

    await igrone_error(query.answer)()

    button = [
        [
            InlineKeyboardButton(
                f"{'✅ ' if regex and str(regex) == str(i) else ''}{i}",
                callback_data=f"uregex_set_{i}",
            )
            for i in range(1, 5)
        ],
        [InlineKeyboardButton("▏ᴅᴇʟᴇᴛᴇ▕", callback_data="uregex_delete")],
        [
            InlineKeyboardButton("⇦ 𝗕𝗔𝗖𝗞", callback_data="mus"),
            InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="close"),
        ],
    ]

    caption_text = (
        simple_caption_txt_format
        .replace("{type}", "Regex/Zfill")
        .replace("{value}", str(regex))
    )

    await retry_on_flood(query.edit_message_media)(
        media=InputMediaPhoto(random.choice(Vars.PICS), caption_text),
        reply_markup=InlineKeyboardMarkup(button),
    )


# ─── Callback: compression quality ───────────────────────────────────────────

def _compress_markup(compress) -> InlineKeyboardMarkup:
    cur = int(compress) if compress else 2
    rows = [
        InlineKeyboardButton(
            f"{'✅ ' if cur == i else ''}{i}",
            callback_data=f"u_compress_set_{i}",
        )
        for i in range(0, 105, 5)
    ]

    button = [rows[x: x + 5] for x in range(0, len(rows), 5)]
    button.append([InlineKeyboardButton("▏ᴅᴇʟᴇᴛᴇ▕", callback_data="u_compress_delete")])
    button.append([
        InlineKeyboardButton("⇦ 𝗕𝗔𝗖𝗞", callback_data="mus"),
        InlineKeyboardButton("▏𝗖𝗟𝗢𝗦𝗘▕", callback_data="close"),
    ])
    return InlineKeyboardMarkup(button)


@Bot.on_callback_query(filters.regex("^u_compress"))
async def compress_handler(_, query):
    user_id = str(query.from_user.id)
    await database.ensure_user(user_id)

    uts = await database.get_settings(user_id)
    compress = uts.get("compress")

    if query.data.startswith("u_compress_set_"):
        compress = query.data.split("_")[-1]
        await database.set_value(user_id, "compress", compress)
        await retry_on_flood(query.answer)(" Sucessfully Added ")

    elif query.data == "u_compress_delete":
        if compress:
            compress = None
            await database.set_value(user_id, "compress", None)
            await retry_on_flood(query.answer)(" Sucessfully Deleted ")
        else:
            await retry_on_flood(query.answer)("📐 𝒀𝒐𝒖 𝒉𝒂𝒔 𝒏𝒐𝒕 𝑺𝒆𝒕 𝑰𝒕 ! 📐")

    # Re-read to confirm
    compress = (await database.get_settings(user_id)).get("compress")

    caption_text = (
        simple_caption_txt_format
        .replace("{type}", "Image Quality")
        .replace("{value}", str(compress))
        + "\n\n<blockquote><b>➥ 100:- Real Quality \n➥ If the image quality is high, the image in the PDF will also be clear, and the file size will be larger. </b></blockquote>"
    )

    await retry_on_flood(query.edit_message_media)(
        media=InputMediaPhoto(random.choice(Vars.PICS), caption_text),
        reply_markup=_compress_markup(compress),
    )


# ─────────────────────────────────────────────────────────────────────────────
# /mybot  — register user's own bot token for auto-channel uploads
# /removebot — remove the stored token
# ─────────────────────────────────────────────────────────────────────────────

from pyrogram import filters as _filters


@Bot.on_message(_filters.command("mybot") & _filters.private)
async def mybot_cmd(client, message):
    """
    Usage: /mybot <BOT_TOKEN>
    Validates the token, stores it, and keeps client ready for on-demand worker tasks.
    """
    from Tools.user_clients import user_client_manager  # noqa: PLC0415
    from Tools.db import database  # noqa: PLC0415

    user_id = str(message.from_user.id)

    # Check if user has already configured a bot
    existing_token = await database.get_bot_token(user_id)
    if existing_token:
        await message.reply(
            "<b>⚠️ Bot Already Set!</b>\n\n"
            "You have already configured a personal bot token.\n"
            "If you want to remove or change it, please use <code>/removebot</code> or <code>/delbot</code> first."
        )
        return

    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.reply(
            "<b>Usage:</b> <code>/mybot YOUR_BOT_TOKEN</code>\n\n"
            "Get a token from @BotFather and add the bot as admin to your channel first.",
        )
        return

    raw_token = args[1].strip()
    sts = await message.reply("<i>Validating token…</i>")

    try:
        bot_info = await user_client_manager.register_token(user_id, raw_token)
    except Exception as e:
        logger.warning(f"[mybot] Error for {user_id}: {e}")
        bot_info = None

    if not bot_info:
        await retry_on_flood(sts.edit)(
            "<b>❌ Invalid token.</b> Make sure you copied the full token from @BotFather."
        )
        return

    bot_name     = bot_info.get("first_name", "Your Bot")
    bot_username = bot_info.get("username", "")
    await retry_on_flood(sts.edit)(
        f"<b>✅ Bot registered!</b>\n\n"
        f"<b>Name:</b> {bot_name}\n"
        f"<b>Username:</b> @{bot_username}\n\n"
        "<i>Auto-uploads to your channels will now use this bot. It will start automatically when a task is created.</i>"
    )


@Bot.on_message(_filters.command(["removebot", "delbot"]) & _filters.private)
async def removebot_cmd(client, message):
    """Remove the stored bot token and stop the per-user client."""
    from Tools.user_clients import user_client_manager  # noqa: PLC0415

    user_id = str(message.from_user.id)
    sts     = await message.reply("<i>Removing bot token…</i>")

    try:
        await user_client_manager.remove_token(user_id)
        await retry_on_flood(sts.edit)(
            "<b>✅ Bot token removed.</b>\n\n"
            "Auto-uploads will be paused until you add a new token via /mybot."
        )
    except Exception as e:
        logger.warning(f"[removebot] Error for {user_id}: {e}")
        await retry_on_flood(sts.edit)("<b>❌ Failed to remove token.</b> Try again.")


async def get_sources_panel(user_id: int | str, page: int = 1):
    """Render interactive inline keyboard for user & admin source management."""
    user_id_str = str(user_id)
    from Webs import web_data  # noqa: PLC0415
    from Tools.db import database  # noqa: PLC0415

    all_sources = list(web_data.items())  # [(name, instance), ...]
    health_data = await database.get_all_sources_health()
    disabled_user_sources = set(await database.get_user_disabled_sources(user_id_str))

    per_page = 10
    total_pages = max(1, (len(all_sources) + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_sources = all_sources[start_idx:end_idx]

    buttons = []
    row = []
    for raw_name, scraper in page_sources:
        sf = scraper.sf
        clean_name = raw_name.strip()
        h_info = health_data.get(sf, {})
        is_auto_disabled = h_info.get("status") == "auto_disabled"

        if is_auto_disabled:
            btn_text = f"⚠️ {clean_name}"
            cb_data = f"src_re_enable:{sf}:{page}"
        elif sf in disabled_user_sources:
            btn_text = f"❌ {clean_name}"
            cb_data = f"src_toggle:{sf}:{page}"
        else:
            btn_text = f"✅ {clean_name}"
            cb_data = f"src_toggle:{sf}:{page}"

        row.append(InlineKeyboardButton(btn_text, callback_data=cb_data))
        if len(row) == 2:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Navigation row
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(" ⬅️ Prev ", callback_data=f"sources_panel:{page-1}"))
    nav_row.append(InlineKeyboardButton(f" Page {page}/{total_pages} ", callback_data="src_noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(" Next ➡️ ", callback_data=f"sources_panel:{page+1}"))
    buttons.append(nav_row)

    # Back / Close row
    buttons.append([
        InlineKeyboardButton(tr(" ⇦ Settings "), callback_data="mus"),
        InlineKeyboardButton(tr(" ✵ Close ✵ "), callback_data="close"),
    ])

    text = (
        "<b>🌐 <u>Source Management Panel</u></b>\n\n"
        "<i>Toggle individual sources to enable or disable them for your requests.\n\n"
        "• <b>✅ Enabled</b>: Active and used for searching/downloading\n"
        "• <b>❌ Disabled</b>: Manually disabled by you\n"
        "• <b>⚠️ Auto Disabled</b>: Automatically disabled due to 3 failed retries (Admins click to re-enable)</i>"
    )
    return text, InlineKeyboardMarkup(buttons)

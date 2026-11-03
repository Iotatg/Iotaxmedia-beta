# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import os
import platform
import sys

import psutil
from pyrogram import __version__, filters, types
from pytgcalls import __version__ as pytgver

from iotaxmedia import app, config, db, lang, userbot
from iotaxmedia.plugins import all_modules


_title_cache: dict = {}
_MEDAL = {1: "🥇", 2: "🥈", 3: "🥉"}


async def _chat_title(chat_id: int) -> str:
    if chat_id in _title_cache:
        return _title_cache[chat_id]
    title = None
    try:
        chat = await app.get_chat(chat_id)
        title = (
            getattr(chat, "title", None)
            or getattr(chat, "first_name", None)
            or str(chat_id)
        )
    except Exception:
        pass
    _title_cache[chat_id] = title
    return title


async def _leaderboard_block(limit: int = 10) -> str:
    """HTML block listing the top-played chats, or empty string if none."""
    try:
        top = await db.get_top_chats(limit)
    except Exception:
        top = []
    if not top:
        return ""
    lines = ["\n<b>🏆 ᴛᴏᴘ 𝟷𝟶 ɢʀᴏᴜᴘꜱ (ꜱᴏɴɢꜱ ᴘʟᴀʏᴇᴅ)</b>"]
    for rank, (cid, plays) in enumerate(top, 1):
        medal = _MEDAL.get(rank, f"<code>{rank}.</code>")
        title = await _chat_title(cid)
        name = title if title else f"<code>{cid}</code>"
        lines.append(f"{medal} <b>{name}</b> — <code>{plays}</code>")
    return "\n".join(lines) + "\n"


@app.on_message(filters.command(["stats"]) & filters.group & ~app.bl_users)
@lang.language()
async def _stats(_, m: types.Message):
    try:
        from iotaxmedia.clone.customization import current_media

        mtype, fid = await current_media("stats_media")
    except Exception:
        mtype, fid = None, None
    if fid:
        send_by_type = {
            "video": m.reply_video,
            "animation": m.reply_animation,
            "document": m.reply_document,
        }
        sender = send_by_type.get(mtype, m.reply_photo)
        media_kw = (
            {"video": fid} if mtype == "video" else
            {"animation": fid} if mtype == "animation" else
            {"document": fid} if mtype == "document" else
            {"photo": fid}
        )
        sent = await sender(**media_kw, caption=m.lang["stats_fetching"])
    else:
        sent = await m.reply_photo(
            photo=config.PING_IMG,
            caption=m.lang["stats_fetching"],
        )

    pid = os.getpid()
    _utext = m.lang["stats_user"].format(
        app.name,
        len(userbot.clients),
        config.AUTO_LEAVE,
        len(db.blacklisted),
        len(app.bl_users),
        len(app.sudoers),
        len(await db.get_chats()),
        len(await db.get_users()),
    )

    try:
        plays_here = await db.get_play_count(m.chat.id)
    except Exception:
        plays_here = 0
    _utext += f"\n<b>🎵 ɢʀᴏᴜᴘ ꜱᴛᴀᴛꜱ</b>\n➥ ᴛʀᴀᴄᴋꜱ ᴘʟᴀʏᴇᴅ ʜᴇʀᴇ » <code>{plays_here}</code>\n"
    _utext += await _leaderboard_block()
    if m.from_user.id in app.sudoers:
        process = psutil.Process(pid)
        storage = psutil.disk_usage("/")
        _utext += m.lang["stats_sudo"].format(
            len(all_modules),
            platform.system(),
            f"{process.memory_info().rss / 1024**2:.2f}",
            round(psutil.virtual_memory().total / (1024.0**3)),
            process.cpu_percent(interval=None),
            psutil.cpu_count(),
            f"{storage.used / (1024.0**3):.2f}",
            f"{storage.total / (1024.0**3):.2f}",
            sys.version.split()[0],
            __version__,
            pytgver,
        )
    await sent.edit_caption(_utext)

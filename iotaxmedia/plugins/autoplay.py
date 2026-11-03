# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
from pyrogram import filters, types

from iotaxmedia import app, db, lang
from iotaxmedia.helpers import can_manage_vc


ON_WORDS = ("on", "enable", "start")
OFF_WORDS = ("off", "disable", "stop")


@app.on_message(filters.command(["autoplay"]) & filters.group & ~app.bl_users)
@lang.language()
@can_manage_vc
async def _autoplay(_, m: types.Message):
    chat_id = m.chat.id


    if len(m.command) < 2:
        current = await db.get_autoplay(chat_id)
        key = "autoplay_on" if current else "autoplay_off"
        return await m.reply_text(m.lang[key].format(m.from_user.mention))

    arg = m.command[1].lower()
    if arg in ON_WORDS:
        status = True
    elif arg in OFF_WORDS:
        status = False
    else:
        return await m.reply_text(m.lang["help_autoplay"])

    await db.set_autoplay(chat_id, status)
    key = "autoplay_on" if status else "autoplay_off"
    await m.reply_text(m.lang[key].format(m.from_user.mention))

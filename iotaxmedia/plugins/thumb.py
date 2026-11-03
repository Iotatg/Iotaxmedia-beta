# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
from pyrogram import filters, types

from iotaxmedia import app, db, lang
from iotaxmedia.helpers import admin_check


@app.on_message(filters.command(["nothumb"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _thumb_hndlr(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(f"<b>Usage:</b>\n\n/{m.command[0]} [enable|disable]")

    arg = m.command[1].lower()
    if arg in ["enable", "on"]:
        await db.set_thumb_mode(m.chat.id, False)
        return await m.reply_text(m.lang["thumb_off"])
    elif arg in ["disable", "off"]:
        await db.set_thumb_mode(m.chat.id, True)
        return await m.reply_text(m.lang["thumb_on"])

    return await m.reply_text(f"<b>Usage:</b>\n\n/{m.command[0]} [enable|disable]")

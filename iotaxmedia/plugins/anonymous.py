# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Per-user Anonymous mode (beta).

When a user turns Anonymous ON, the bot hides their identifying details
(name / username / id / role flags) from other users in /info lookups
and shows a generic anonymous name as the requester of any streaming
(now-playing / queued) message.

Scope: global per-user toggle (the user's preference, applied in every
chat). The user themselves can still see their own details — masking
only applies when *another* user looks them up.

DB helpers: `db.is_anon(uid)`, `db.set_anon(uid, on)` (see core/mongo.py).
"""
from pyrogram import filters, types

from iotaxmedia import app, db, lang


ANON_NAME = "anonymous"
ANON_INFO = "🚫 This is a Anonymous User."


@app.on_message(filters.command(["anonymous", "anon"]) & ~app.bl_users)
@lang.language()
async def anonymous_toggle(_, m: types.Message):
    if not m.from_user:
        return

    if len(m.command) < 2:
        on = await db.is_anon(m.from_user.id)
        state = "ON ✅" if on else "OFF ❌"
        return await m.reply_text(
            "🕶️ <b>Anonymous Mode</b>\n"
            f"➤ Status: {state}\n\n"
            "Usage:\n"
            "• <code>/anonymous on</code> — hide your details from /info and the streaming requester field\n"
            "• <code>/anonymous off</code> — show your details normally"
        )

    arg = m.command[1].lower()
    if arg not in ("on", "off"):
        return await m.reply_text(
            "❌ Invalid argument. Use <code>/anonymous on</code> or <code>/anonymous off</code>."
        )

    turn_on = arg == "on"
    await db.set_anon(m.from_user.id, turn_on)
    if turn_on:
        await m.reply_text(
            "🕶️ <b>Anonymous Mode ENABLED</b>\n"
            "➤ Your details will be hidden from other users in /info "
            "and the streaming requester field."
        )
    else:
        await m.reply_text(
            "✅ <b>Anonymous Mode DISABLED</b>\n"
            "➤ Your details are visible again."
        )

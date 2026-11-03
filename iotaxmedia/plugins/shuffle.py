# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import random

from pyrogram import filters, types

from iotaxmedia import app, lang, queue
from iotaxmedia.helpers import can_manage_vc


@app.on_message(
    filters.command(["shuffle", "cshuffle"]) & filters.group & ~app.bl_users
)
@lang.language()
@can_manage_vc
async def _shuffle(_, m: types.Message):
    items = queue.get_queue(m.chat.id)
    if not items:
        return await m.reply_text(m.lang["shuffle_none"])
    if len(items) < 3:
        return await m.reply_text(m.lang["shuffle_only"])

    current = items[0]
    rest = list(items[1:])
    random.shuffle(rest)

    dq = queue.queues[m.chat.id]
    dq.clear()
    dq.append(current)
    for item in rest:
        dq.append(item)

    await m.reply_text(m.lang["shuffle_done"].format(m.from_user.mention))

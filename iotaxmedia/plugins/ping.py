# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import time

import psutil
from pyrogram import filters, types

from iotaxmedia import app, iotaxmedia, boot, config, lang
from iotaxmedia.helpers import buttons


@app.on_message(filters.command(["alive", "ping"]) & ~app.bl_users)
@lang.language()
async def _ping(_, m: types.Message):
    start = time.time()
    sent = await m.reply_text(m.lang["pinging"])

    def get_time(s):
        return (
            lambda r: (
                (f"{r[-1]}, " if r[-1][:-4] != "0" else "") + ":".join(reversed(r[:-1]))
            )
        )(
            [
                f"{v}{u}"
                for v, u in zip(
                    [s % 60, (s // 60) % 60, (s // 3600) % 24, s // 86400],
                    ["s", "m", "h", "days"],
                )
            ]
        )

    uptime = get_time(int(time.time() - boot))
    latency = round((time.time() - start) * 1000, 2)
    caption = m.lang["ping_pong"].format(
        latency,
        uptime,
        psutil.cpu_percent(interval=0),
        psutil.virtual_memory().percent,
        psutil.disk_usage("/").percent,
        await iotaxmedia.ping(),
    )
    try:
        from iotaxmedia.clone.customization import current_media

        mtype, fid = await current_media("ping_media")
    except Exception:
        mtype, fid = None, None
    if fid:
        media_cls = {
            "video": types.InputMediaVideo,
            "animation": types.InputMediaAnimation,
            "document": types.InputMediaDocument,
        }.get(mtype, types.InputMediaPhoto)
        await sent.edit_media(
            media=media_cls(media=fid, caption=caption),
            reply_markup=buttons.ping_markup(m.lang["support"]),
        )
    else:
        await sent.edit_media(
            media=types.InputMediaPhoto(media=config.PING_IMG, caption=caption),
            reply_markup=buttons.ping_markup(m.lang["support"]),
        )

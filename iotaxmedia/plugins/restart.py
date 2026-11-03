# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import asyncio
import os
import shutil
import sys

from pyrogram import filters, types

from iotaxmedia import app, db, lang, stop


@app.on_message(filters.command(["logs"]) & app.sudoers)
@lang.language()
async def _logs(_, m: types.Message):
    sent = await m.reply_text(m.lang["log_fetch"])
    if not os.path.exists("log.txt"):
        return await sent.edit_text(m.lang["log_not_found"])
    await sent.edit_media(
        media=types.InputMediaDocument(
            media="log.txt",
            caption=m.lang["log_sent"].format(app.name),
        )
    )


@app.on_message(filters.command(["logger"]) & app.sudoers)
@lang.language()
async def _logger(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(m.lang["logger_usage"].format(m.command[0]))
    if m.command[1] not in ("on", "off"):
        return await m.reply_text(m.lang["logger_usage"].format(m.command[0]))

    if m.command[1] == "on":
        await db.set_logger(True)
        await m.reply_text(m.lang["logger_on"])
    else:
        await db.set_logger(False)
        await m.reply_text(m.lang["logger_off"])


@app.on_message(filters.command(["restart"]) & app.sudoers)
@lang.language()
async def _restart(_, m: types.Message):


    from iotaxmedia import config
    from iotaxmedia.clone.runtime_inproc import parent_module

    token = getattr(config, "CLONE_TOKEN", None)
    if token:
        sent = await m.reply_text(m.lang["restarting"])
        parent_rt = parent_module("iotaxmedia.clone.runtime")
        if parent_rt is None:
            return await sent.edit_text("Restart unavailable right now.")
        parent_rt.get_manager().schedule_bounce(token, delay=0.0)
        return await sent.edit_text(
            m.lang["restarted"] + "\n\n(ᴄʟᴏɴᴇ ʀᴇsᴛᴀʀᴛɪɴɢ…)"
        )

    sent = await m.reply_text(m.lang["restarting"])

    for directory in ["cache", "downloads"]:
        shutil.rmtree(directory, ignore_errors=True)

    await sent.edit_text(m.lang["restarted"])

    try:
        await asyncio.wait_for(stop(), timeout=10)
    except Exception:
        pass

    try:
        os.remove("log.txt")
    except Exception:
        pass

    os.execl(sys.executable, sys.executable, "-m", "iotaxmedia")

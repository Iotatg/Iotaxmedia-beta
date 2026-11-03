# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Clone owner customization commands (per-clone, owner-only).

Settings persist in Mongo via iotaxmedia.clone.customization; senders read
them at call time. Media setters persist the media TYPE so video/GIF render
correctly instead of guessing from file_id prefixes.
"""

import logging

from pyrogram import filters
from pyrogram.types import Message

import iotaxmedia.clone.customization as cust

logger = logging.getLogger("iotaxmedia.clone")


def _extract_media(message: Message):
    """Return (media_type, file_id) from a message or its reply target."""
    for msg in (message.reply_to_message, message):
        if msg is None:
            continue
        if msg.photo:
            return "photo", msg.photo.file_id
        if msg.video:
            return "video", msg.video.file_id
        if msg.animation:
            return "animation", msg.animation.file_id
        if msg.document and (msg.document.mime_type or "").startswith("image/"):
            return "document", msg.document.file_id
    return None, None


def register(app, token: str, owner_id: int):
    owner_flt = filters.user(owner_id) & filters.private

    def _cmd(*names, group=100):
        return app.on_message(
            filters.command(list(names)) & owner_flt, group=group
        )

    @_cmd("setstart", "setupic")
    async def _set_start(_, m: Message):
        mtype, fid = _extract_media(m)
        caption = m.text.split(None, 1)[1] if len(m.command) > 1 else None
        if fid:
            await cust.set_start_media(token, fid, mtype)
            if caption:
                await cust.set_start_message(token, caption)
            extra = " (+caption)" if caption else ""
            return await m.reply_text(f"**✅ ꜱᴛᴀʀᴛ ᴍᴇᴅɪᴀ ꜱᴀᴠᴇᴅ ({mtype}){extra} ✔**")
        if caption:
            await cust.set_start_message(token, caption)
            return await m.reply_text("**✅ ꜱᴛᴀʀᴛ ᴍᴇꜱꜱᴀɢᴇ ꜱᴀᴠᴇᴅ ✔**")
        return await m.reply_text(
            "**❍ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ/ᴠɪᴅᴇᴏ/ɢɪꜰ ᴡɪᴛʜ /setstart\n"
            "➥ ᴏʀ ᴀᴅᴅ ᴛᴇxᴛ ᴀꜰᴛᴇʀ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅ ᴛᴏ ꜱᴇᴛ ᴛʜᴇ ꜱᴛᴀʀᴛ ᴍᴇꜱꜱᴀɢᴇ.**"
        )

    @_cmd("delstart", "delstartpic")
    async def _del_start(_, m: Message):
        await cust.del_start_media(token)
        await m.reply_text("**✅ ᴄᴜꜱᴛᴏᴍ ꜱᴛᴀʀᴛ ᴍᴇᴅɪᴀ ʀᴇᴍᴏᴠᴇᴅ ✔**")

    @_cmd("setstartmsg", "setstartmessage")
    async def _set_start_msg(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /setstartmsg <text>")
        await cust.set_start_message(token, m.text.split(None, 1)[1])
        await m.reply_text("**✅ ꜱᴛᴀʀᴛ ᴍᴇꜱꜱᴀɢᴇ ꜱᴀᴠᴇᴅ ✔**")

    @_cmd("delstartmsg", "delstartmessage")
    async def _del_start_msg(_, m: Message):
        await cust.del_start_message(token)
        await m.reply_text("**✅ ꜱᴛᴀʀᴛ ᴍᴇꜱꜱᴀɢᴇ ʀᴇᴍᴏᴠᴇᴅ ✔**")

    @_cmd("setpingpic", "setpingimg")
    async def _set_ping(_, m: Message):
        mtype, fid = _extract_media(m)
        if not fid:
            return await m.reply_text(
                "**❍ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ/ᴠɪᴅᴇᴏ/ɢɪꜰ ᴡɪᴛʜ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ✔**"
            )
        await cust.set_ping_media(token, fid, mtype)
        await m.reply_text(f"**✅ ᴘɪɴɢ ᴍᴇᴅɪᴀ ꜱᴀᴠᴇᴅ ({mtype}) ✔**")

    @_cmd("delpingpic", "delpingimg")
    async def _del_ping(_, m: Message):
        await cust.del_ping_media(token)
        await m.reply_text("**✅ ᴘɪɴɢ ᴍᴇᴅɪᴀ ʀᴇᴍᴏᴠᴇᴅ ✔**")

    @_cmd("setstatspic", "setstatsimg")
    async def _set_stats(_, m: Message):
        mtype, fid = _extract_media(m)
        if not fid:
            return await m.reply_text(
                "**❍ ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴘʜᴏᴛᴏ/ᴠɪᴅᴇᴏ/ɢɪꜰ ᴡɪᴛʜ ᴛʜɪꜱ ᴄᴏᴍᴍᴀɴᴅ ✔**"
            )
        await cust.set_stats_media(token, fid, mtype)
        await m.reply_text(f"**✅ ꜱᴛᴀᴛꜱ ᴍᴇᴅɪᴀ ꜱᴀᴠᴇᴅ ({mtype}) ✔**")

    @_cmd("delstatspic", "delstatsimg")
    async def _del_stats(_, m: Message):
        await cust.del_stats_media(token)
        await m.reply_text("**✅ ꜱᴛᴀᴛꜱ ᴍᴇᴅɪᴀ ʀᴇᴍᴏᴠᴇᴅ ✔**")

    @_cmd("setchannel")
    async def _set_channel(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /setchannel <channel link>")
        await cust.set_clone_channel(token, m.command[1])
        await m.reply_text("**✅ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋ ꜱᴀᴠᴇᴅ ✔**")

    @_cmd("setsupport")
    async def _set_support(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /setsupport <chat link>")
        await cust.set_clone_support(token, m.command[1])
        await m.reply_text("**✅ ꜱᴜᴘᴘᴏʀᴛ ʟɪɴᴋ ꜱᴀᴠᴇᴅ ✔**")

    @_cmd("setstring", "setsession")
    async def _set_string(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /setstring <session>")
        session = m.text.split(None, 1)[1].strip()
        await cust.del_clone_string(token)
        await cust.set_clone_string(token, session)
        from iotaxmedia.clone.runtime_inproc import parent_module

        parent_module("iotaxmedia.clone.runtime").get_manager().schedule_bounce(token)
        await m.reply_text(
            "**✅ ꜱᴇꜱꜱɪᴏɴ ꜱᴀᴠᴇᴅ ✔**\n\n"
            "➥ ʏᴏᴜʀ ᴄʟᴏɴᴇ ʀᴇꜱᴛᴀʀᴛꜱ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ɪɴ ~1 ᴍɪɴᴜᴛᴇ "
            "ᴡɪᴛʜ ɪᴛꜱ ᴏᴡɴ ᴀꜱꜱɪꜱᴛᴀɴᴛꜱ — ɴᴏ ɴᴇᴇᴅ ꜰᴏʀ /restart."
        )

    @_cmd("delstring", "delsession")
    async def _del_string(_, m: Message):
        await cust.del_clone_string(token)
        from iotaxmedia.clone.runtime_inproc import parent_module

        parent_module("iotaxmedia.clone.runtime").get_manager().schedule_bounce(token)
        await m.reply_text(
            "**✅ ꜱᴇꜱꜱɪᴏɴ ʀᴇᴍᴏᴠᴇᴅ ✔**\n\n"
            "➥ ᴄʟᴏɴᴇ ʀᴇꜱᴛᴀʀᴛꜱ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴏɴ ꜱʜᴀʀᴇᴅ ᴀꜱꜱɪꜱᴛᴀɴᴛꜱ ɪɴ ~1 ᴍɪɴᴜᴛᴇ."
        )

    @_cmd("setmongodb", "setmongo")
    async def _set_mongo(_, m: Message):



        await m.reply_text(
            "**⚠️ ᴘᴇʀ-ᴄʟᴏɴᴇ ᴍᴏɴɢᴏᴅʙ ɪꜱ ɴᴏᴛ ꜱᴜᴘᴘᴏʀᴛᴇᴅ ʏᴇᴛ.**\n\n"
            "➥ ꜱᴇᴛᴛɪɴɢꜱ ꜱᴛᴀʏ ɪɴ ᴛʜᴇ ᴍᴀɪɴ ᴅᴀᴛᴀʙᴀꜱᴇ — ɴᴏᴛʜɪɴɢ ᴡᴀꜱ ᴄʜᴀɴɢᴇᴅ."
        )

    @_cmd("delmongodb", "delmongo")
    async def _del_mongo(_, m: Message):
        await cust.del_clone_mongo(token)
        await m.reply_text("**❍ ɴᴏᴛʜɪɴɢ ᴛᴏ ʀᴇᴍᴏᴠᴇ — ᴘᴇʀ-ᴄʟᴏɴᴇ ᴍᴏɴɢᴏ ɪꜱ ᴜɴᴜꜱᴇᴅ.**")

    @_cmd("chatbot")
    async def _chatbot(_, m: Message):
        enabled = not await cust.get_clone_chatbot(token)
        await cust.set_clone_chatbot(token, enabled)
        await m.reply_text(f"**❍ ᴄʜᴀᴛʙᴏᴛ ɪꜱ ɴᴏᴡ {'ᴏɴ ✔' if enabled else 'ᴏꜰꜰ ✘'}**")

    @_cmd("name", "setname", "botname")
    async def _set_name(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /name <new bot name>")
        name = m.text.split(None, 1)[1]
        await cust.set_clone_name(token, name[:64])
        await m.reply_text(
            "**✅ ᴅɪꜱᴘʟᴀʏ ɴᴀᴍᴇ ꜱᴀᴠᴇᴅ ✔**\n\n➥ ɴᴇxᴛ ʀᴇꜱᴛᴀʀᴛ (/restart) ᴘᴀ ᴀᴘᴘʟʏ ʜᴏɢᴀ."
        )

    @_cmd("setlogger", "logger")
    async def _set_logger(_, m: Message):
        if len(m.command) < 2 or not str(m.command[1]).lstrip("-").isdigit():
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /setlogger <chat_id>")
        await cust.set_clone_logger(token, int(m.command[1]))
        await m.reply_text("**✅ ʟᴏɢ ᴄʜᴀᴛ ꜱᴀᴠᴇᴅ ✔**\n\n➥ ɴᴇxᴛ ʀᴇꜱᴛᴀʀᴛ ᴘᴀ ᴀᴘᴘʟʏ ʜᴏɢᴀ.")

    @_cmd("dellogger")
    async def _del_logger(_, m: Message):
        await cust.del_clone_logger(token)
        await m.reply_text("**✅ ʟᴏɢ ᴄʜᴀᴛ ʀᴇᴍᴏᴠᴇᴅ ✔**\n\n➥ ɴᴇxᴛ ʀᴇꜱᴛᴀʀᴛ ᴘᴀ ᴀᴘᴘʟʏ ʜᴏɢᴀ.")

    @_cmd("setchannelname")
    async def _set_channel_name(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /setchannelname <button name>")
        await cust.set_clone_channel_name(token, m.text.split(None, 1)[1][:32])
        await m.reply_text("**✅ ᴄʜᴀɴɴᴇʟ ʙᴜᴛᴛᴏɴ ɴᴀᴍᴇ ꜱᴀᴠᴇᴅ ✔**")

    @_cmd("delchannelname")
    async def _del_channel_name(_, m: Message):
        await cust.del_clone_channel_name(token)
        await m.reply_text("**✅ ᴄʜᴀɴɴᴇʟ ʙᴜᴛᴛᴏɴ ɴᴀᴍᴇ ʀᴇᴍᴏᴠᴇᴅ ✔**")

    @_cmd("setsupportname")
    async def _set_support_name(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /setsupportname <button name>")
        await cust.set_clone_support_name(token, m.text.split(None, 1)[1][:32])
        await m.reply_text("**✅ ꜱᴜᴘᴘᴏʀᴛ ʙᴜᴛᴛᴏɴ ɴᴀᴍᴇ ꜱᴀᴠᴇᴅ ✔**")

    @_cmd("delsupportname")
    async def _del_support_name(_, m: Message):
        await cust.del_clone_support_name(token)
        await m.reply_text("**✅ ꜱᴜᴘᴘᴏʀᴛ ʙᴜᴛᴛᴏɴ ɴᴀᴍᴇ ʀᴇᴍᴏᴠᴇᴅ ✔**")

    @_cmd("setownername")
    async def _set_owner_name(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /setownername <button name>")
        await cust.set_clone_owner_name(token, m.text.split(None, 1)[1][:32])
        await m.reply_text("**✅ ᴏᴡɴᴇʀ ʙᴜᴛᴛᴏɴ ɴᴀᴍᴇ ꜱᴀᴠᴇᴅ ✔**")

    @_cmd("delownername")
    async def _del_owner_name(_, m: Message):
        await cust.del_clone_owner_name(token)
        await m.reply_text("**✅ ᴏᴡɴᴇʀ ʙᴜᴛᴛᴏɴ ɴᴀᴍᴇ ʀᴇᴍᴏᴠᴇᴅ ✔**")

    def _btn_toggle(key, en_cmd, dis_cmd, label):
        @_cmd(en_cmd)
        async def _en(_, m: Message, k=key, lab=label):
            await cust.set_btn_enabled(token, k, True)
            await m.reply_text(f"**✅ {lab} ʙᴜᴛᴛᴏɴ ᴇɴᴀʙʟᴇᴅ ✔**")

        @_cmd(dis_cmd)
        async def _dis(_, m: Message, k=key, lab=label):
            await cust.set_btn_enabled(token, k, False)
            await m.reply_text(f"**✅ {lab} ʙᴜᴛᴛᴏɴ ᴅɪꜱᴀʙʟᴇᴅ ✔**")

    _btn_toggle("help", "enhelpbtn", "dishelpbtn", "ʜᴇʟᴘ")
    _btn_toggle("clone", "enclonebtn", "disclonebtn", "ᴀᴅᴅ ᴍᴇ")
    _btn_toggle("support", "ensupportbtn", "dissupportbtn", "ꜱᴜᴘᴘᴏʀᴛ")
    _btn_toggle("channel", "enchannelbtn", "dischannelbtn", "ᴄʜᴀɴɴᴇʟ")
    _btn_toggle("owner", "enownerbtn", "disownerbtn", "ᴏᴡɴᴇʀ")
    _btn_toggle("language", "enlangbtn", "dislangbtn", "ʟᴀɴɢᴜᴀɢᴇ")

    @_cmd("addbtn")
    async def _add_btn(_, m: Message):
        if len(m.command) < 3:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /addbtn <name> <link>")
        name, url = m.command[1], m.command[2]
        if not url.startswith(("http://", "https://", "tg://", "t.me")):
            return await m.reply_text("**❍ ɢɪᴠᴇ ᴀ ᴠᴀʟɪᴅ ʟɪɴᴋ.**")
        await cust.add_extra_button(token, name, url)
        await m.reply_text(f"**✅ ʙᴜᴛᴛᴏɴ `{name}` ᴀᴅᴅᴇᴅ ✔**")

    @_cmd("delbtn")
    async def _del_btn(_, m: Message):
        if len(m.command) < 2:
            return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /delbtn <name>")
        ok = await cust.del_extra_button(token, m.command[1])
        if ok:
            return await m.reply_text("**✅ ʙᴜᴛᴛᴏɴ ʀᴇᴍᴏᴠᴇᴅ ✔**")
        await m.reply_text("**❍ ʙᴜᴛᴛᴏɴ ɴᴏᴛ ꜰᴏᴜɴᴅ.**")

    @_cmd("clearbtns", "delallbtn")
    async def _clear_btns(_, m: Message):
        await cust.clear_extra_buttons(token)
        await m.reply_text("**✅ ᴀʟʟ ᴄᴜꜱᴛᴏᴍ ʙᴜᴛᴛᴏɴꜱ ʀᴇᴍᴏᴠᴇᴅ ✔**")

    logger.info(f"Clone customization handlers registered ({token.split(':')[0]}).")

# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Clone /start override: custom media (typed) + text, buttons kept.

Registered in group -1 so it wins over the default plugin handler; it always
stop_propagation()s to avoid double replies on clones.
"""

import logging

from pyrogram import enums, filters
from pyrogram.types import Message

logger = logging.getLogger("iotaxmedia.clone")

START_OVERRIDE_GROUP = -1


async def _clone_start_key(token: str, lang: dict, private: bool, buttons):
    from iotaxmedia import app, config
    from iotaxmedia.clone.customization import (
        get_clone_channel_name,
        get_clone_support_name,
        get_clone_owner_name,
        is_btn_enabled,
        get_extra_buttons,
    )

    channel_name = await get_clone_channel_name(token) or lang.get("channel", "channel")
    support_name = await get_clone_support_name(token) or lang.get("support", "support")
    owner_name = await get_clone_owner_name(token) or lang.get("owner", "owner")
    rows = []
    if await is_btn_enabled(token, "clone") and getattr(app, "username", None):
        rows.append(
            [
                buttons.ikb(
                    text=lang.get("add_me", "add me"),
                    url=f"https://t.me/{app.username}?startgroup=true",
                )
            ]
        )
    mid = []
    if await is_btn_enabled(token, "support"):
        mid.append(buttons.ikb(text=support_name, url=config.SUPPORT_CHAT))
    if await is_btn_enabled(token, "channel"):
        mid.append(buttons.ikb(text=channel_name, url=config.SUPPORT_CHANNEL))
    if mid:
        rows.append(mid)
    bot = []
    if await is_btn_enabled(token, "help"):
        bot.append(buttons.ikb(text=lang.get("help", "help"), callback_data="help"))
    if await is_btn_enabled(token, "owner"):
        owner_url = (
            f"tg://user?id={config.CLONE_OWNER_ID}"
            if getattr(config, "CLONE_OWNER_ID", 0)
            else config.OWNER_LINK
        )
        bot.append(buttons.ikb(text=owner_name, url=owner_url))
    if bot:
        rows.append(bot)
    if not private and await is_btn_enabled(token, "language"):
        rows.append(
            [buttons.ikb(text=lang.get("language", "language"), callback_data="language")]
        )
    extras = await get_extra_buttons(token)
    for extra in extras:
        rows.append([buttons.ikb(text=extra["name"], url=extra["url"])])
    if not rows:
        return None
    return buttons.ikm(rows)


async def _send_typed(message: Message, mtype, fid, caption, key, private):
    """Dispatch stored media by its persisted type; False on any failure."""
    kw = dict(caption=caption, reply_markup=key, parse_mode=enums.ParseMode.HTML)
    try:
        if mtype == "video":
            await message.reply_video(video=fid, quote=not private, **kw)
            return True
        if mtype == "animation":
            await message.reply_animation(animation=fid, quote=not private, **kw)
            return True
        if mtype == "document":
            await message.reply_document(document=fid, quote=not private, **kw)
            return True

        await message.reply_photo(photo=fid, quote=not private, **kw)
        return True
    except Exception as e:
        logger.warning(f"Custom start media send failed ({mtype}): {e}")
        return False


def register(app, token: str):
    from iotaxmedia import config, db, lang as lang_mod
    from iotaxmedia.helpers import buttons
    from iotaxmedia.clone.customization import (
        get_start_media,
        get_start_message,
        parse_media,
        get_clone_channel_name,
        get_clone_support_name,
        get_clone_owner_name,
        is_btn_enabled,
        get_extra_buttons,
    )

    async def _panel_text(message: Message, private: bool) -> str:
        custom = await get_start_message(token)
        if custom:
            return custom
        _lang = getattr(message, "lang", None) or {}
        bot_user = getattr(app.me, "username", None)


        bot_display = getattr(app.me, "first_name", None) or "𝐈ᴏᴛᴀ ✘ ʙєᴛᴀ"
        bot_name = (
            f"<a href='https://t.me/{bot_user}'>{bot_display}</a>"
            if bot_user
            else bot_display
        )
        base = (
            (_lang.get("start_pm") or "Hey {0}, I am {1}!")
            if private
            else (_lang.get("start_gp") or "I am {1}!")
        )
        return (
            base.format(message.from_user.first_name, bot_name)
            if private
            else base.format(bot_name)
        )

    @app.on_message(filters.command(["start"]), group=START_OVERRIDE_GROUP)
    @lang_mod.language()
    async def _start_override(_, message: Message):
        user = message.from_user
        if user is None:
            return
        _lang = getattr(message, "lang", None) or {}

        if user.id in app.bl_users and user.id not in db.notified:
            await message.reply_text(_lang.get("bl_user_notify", "You are blocked."))
            return await message.stop_propagation()

        private = message.chat.type == enums.ChatType.PRIVATE
        text = await _panel_text(message, private)

        key = await _clone_start_key(token, getattr(message, "lang", {}) or {}, private, buttons)
        if key is None:
            key = buttons.start_key(getattr(message, "lang", {}) or {}, private)

        mtype, fid = parse_media(await get_start_media(token))
        sent = False
        if fid:
            sent = await _send_typed(message, mtype, fid, text, key, private)
        if not sent:
            from iotaxmedia.helpers._assets import start_video

            await message.reply_video(
                video=start_video(config.START_VIDEO),
                caption=text,
                reply_markup=key,
                quote=not private,
                parse_mode=enums.ParseMode.HTML,
            )

        if private:
            if not await db.is_user(user.id):
                await db.add_user(user.id)
        elif not await db.is_chat(message.chat.id):
            await db.add_chat(message.chat.id)
        return await message.stop_propagation()

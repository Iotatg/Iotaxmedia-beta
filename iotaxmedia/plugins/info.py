# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import asyncio

from pyrogram import enums, filters, types

from iotaxmedia import app, db, lang
from iotaxmedia.helpers import utils
from iotaxmedia.plugins.anonymous import ANON_INFO


@app.on_message(filters.command(["info", "userinfo"]) & ~app.bl_users)
@lang.language()
async def _info(_, m: types.Message):
    user = await utils.extract_user(m) or m.from_user
    requester = m.from_user



    if (
        requester
        and user
        and not user.is_bot
        and requester.id != user.id
        and await db.is_anon(user.id)
    ):
        return await m.reply_text(ANON_INFO)

    sent = await m.reply_text(m.lang.get("info_fetching", "Fetching user info..."))


    photo = None
    if user.photo:
        try:
            photo = await app.download_media(user.photo.big_file_id)
        except Exception:
            photo = None


    is_owner = user.id == app.owner
    is_sudo = user.id in app.sudoers
    is_admin = False
    try:
        member = await app.get_chat_member(m.chat.id, user.id)
        is_admin = member.status in (
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER,
        )
    except Exception:
        pass


    common = 0
    try:
        common = len(await app.get_common_chats(user.id))
    except Exception:
        common = 0

    full_name = " ".join(filter(None, [user.first_name, user.last_name])) or "—"
    username = f"@{user.username}" if user.username else "—"
    dc = user.dc_id or "—"

    text = (
        f"<b>👤 {m.lang.get('info_title', 'User Information')}</b>\n\n"
        f"<b>{m.lang.get('info_name', 'Name')}:</b> {full_name}\n"
        f"<b>{m.lang.get('info_id', 'ID')}:</b> <code>{user.id}</code>\n"
        f"<b>{m.lang.get('info_username', 'Username')}:</b> {username}\n"
        f"<b>{m.lang.get('info_mention', 'Mention')}:</b> {user.mention}\n"
        f"<b>{m.lang.get('info_dc', 'DC')}:</b> {dc}\n"
        f"<b>{m.lang.get('info_premium', 'Premium')}:</b> {'✅' if user.is_premium else '❌'}\n"
        f"<b>{m.lang.get('info_bot', 'Bot')}:</b> {'✅' if user.is_bot else '❌'}\n"
        f"<b>{m.lang.get('info_owner', 'Owner')}:</b> {'✅' if is_owner else '❌'}\n"
        f"<b>{m.lang.get('info_sudo', 'Sudo')}:</b> {'✅' if is_sudo else '❌'}\n"
        f"<b>{m.lang.get('info_admin', 'Admin in chat')}:</b> {'✅' if is_admin else '❌'}\n"
        f"<b>{m.lang.get('info_common', 'Common chats')}:</b> {common}"
    )

    try:
        if photo:
            await sent.delete()
            await m.reply_photo(photo=photo, caption=text)
        else:
            await sent.edit_text(text)
    except Exception:
        try:
            await sent.edit_text(text)
        except Exception:
            pass
    finally:
        if photo:
            try:
                __import__("os").remove(photo)
            except Exception:
                pass

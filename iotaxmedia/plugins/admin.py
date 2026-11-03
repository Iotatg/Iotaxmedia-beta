# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import re
from datetime import datetime, timedelta

from pyrogram import filters, types
from pyrogram.types import ChatPermissions, ChatPrivileges

from iotaxmedia import app, db, lang
from iotaxmedia.helpers import admin_check, is_admin, utils


MUTED_PERMS = ChatPermissions(
    can_send_messages=False,
    can_send_audios=False,
    can_send_documents=False,
    can_send_photos=False,
    can_send_videos=False,
    can_send_video_notes=False,
    can_send_voice_notes=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
    can_manage_topics=False,
)


PROMOTE_RIGHTS = ChatPrivileges(
    can_manage_chat=True,
    can_delete_messages=True,
    can_manage_video_chats=True,
    can_restrict_members=True,
    can_invite_users=True,
    can_pin_messages=True,
    can_change_info=True,
    can_promote_members=False,
)


FULLPROMOTE_RIGHTS = ChatPrivileges(
    can_manage_chat=True,
    can_delete_messages=True,
    can_manage_video_chats=True,
    can_restrict_members=True,
    can_invite_users=True,
    can_pin_messages=True,
    can_change_info=True,
    can_promote_members=True,
    is_anonymous=False,
)


DEMOTE_RIGHTS = ChatPrivileges(
    is_anonymous=False,
    can_manage_chat=False,
    can_delete_messages=False,
    can_manage_video_chats=False,
    can_restrict_members=False,
    can_promote_members=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
    can_manage_topics=False,
)

_DURATION_RE = re.compile(r"^(\d+)([mhd])$", re.IGNORECASE)
_UNIT_SECONDS = {"m": 60, "h": 3600, "d": 86400}


def _txt(m: types.Message, key: str, default: str) -> str:
    return m.lang.get(key, default)


def parse_duration(command: list[str]) -> tuple[int | None, str | None]:
    """Return (seconds, human) parsed from a trailing 10m/2h/1d token."""
    for token in command[1:]:
        match = _DURATION_RE.match(token)
        if match:
            value, unit = int(match.group(1)), match.group(2).lower()
            return value * _UNIT_SECONDS[unit], f"{value}{unit}"
    return None, None


async def _protected(m: types.Message, user: types.User) -> str | None:
    """Return an error string if the target must not be actioned, else None."""
    if user.id == app.id:
        return _txt(m, "admin_cant_self", "I can't perform that action on myself.")
    if user.id == app.owner or user.id in app.sudoers:
        return _txt(m, "admin_cant_owner", "That user is protected and can't be targeted.")
    return None


def _resolve_target(m: types.Message):
    """Resolve a target user from a command message. Returns a COROUTINE
    that the caller should await. (We return a coroutine rather than a
    user so the async/await semantics stay explicit.)

    Skips text-mention entities that Telegram may auto-create when the
    command is parsed (e.g. /fullpromote@botname).
    """
    async def _resolve():
        if m.reply_to_message and m.reply_to_message.from_user:
            return m.reply_to_message.from_user
        if m.text:
            import re






            m_at = re.search(r"@(\w{5,32})", m.text)
            m_id = re.search(r"\b(\d{6,15})\b", m.text)
            if m_at:
                try:
                    return await app.get_users("@" + m_at.group(1))
                except Exception:
                    return None
            if m_id:
                try:
                    return await app.get_users(int(m_id.group(1)))
                except Exception:
                    return None
        return None
    return _resolve()


async def _safe_extract_user(m: types.Message) -> types.User | None:
    """Like utils.extract_user but won't return the bot itself when the
    message has a text-mention entity pointing to the bot (e.g. from
    /command@botname syntax)."""
    target = await _resolve_target(m)
    if target and target.id == app.id:
        return None
    return target


@app.on_message(filters.command(["mute", "unmute"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _mute(_, m: types.Message):
    user = await _safe_extract_user(m)
    if not user:
        return await m.reply_text(m.lang["user_not_found"])

    if m.command[0] == "mute":
        if error := await _protected(m, user):
            return await m.reply_text(error)
        if await is_admin(m.chat.id, user.id):
            return await m.reply_text(
                _txt(m, "admin_cant_admin", "You can't restrict an admin.")
            )

        seconds, human = parse_duration(m.command)
        until = datetime.now() + timedelta(seconds=seconds) if seconds else None
        try:
            await app.restrict_chat_member(
                m.chat.id,
                user.id,
                MUTED_PERMS,
                until_date=until or datetime(1970, 1, 1),
            )
        except Exception as ex:
            return await m.reply_text(
                _txt(m, "admin_bot_no_rights", "Failed. Reason: <code>{0}</code>").format(
                    type(ex).__name__
                )
            )
        suffix = f" ({human})" if human else ""
        return await m.reply_text(
            _txt(m, "admin_muted", "🔇 Muted {0}{1}.").format(user.mention, suffix)
        )

    try:
        perms = (await app.get_chat(m.chat.id)).permissions or ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )
        await app.restrict_chat_member(m.chat.id, user.id, perms)
    except Exception as ex:
        return await m.reply_text(
            _txt(m, "admin_bot_no_rights", "Failed. Reason: <code>{0}</code>").format(
                type(ex).__name__
            )
        )
    await m.reply_text(
        _txt(m, "admin_unmuted", "🔊 Unmuted {0}.").format(user.mention)
    )


@app.on_message(filters.command(["ban", "unban"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _ban(_, m: types.Message):
    user = await _safe_extract_user(m)
    if not user:
        return await m.reply_text(m.lang["user_not_found"])

    if m.command[0] == "ban":
        if error := await _protected(m, user):
            return await m.reply_text(error)
        if await is_admin(m.chat.id, user.id):
            return await m.reply_text(
                _txt(m, "admin_cant_admin", "You can't restrict an admin.")
            )

        seconds, human = parse_duration(m.command)
        until = datetime.now() + timedelta(seconds=seconds) if seconds else None
        try:
            await app.ban_chat_member(
                m.chat.id, user.id, until_date=until or datetime(1970, 1, 1)
            )
        except Exception as ex:
            return await m.reply_text(
                _txt(m, "admin_bot_no_rights", "Failed. Reason: <code>{0}</code>").format(
                    type(ex).__name__
                )
            )
        suffix = f" ({human})" if human else ""
        return await m.reply_text(
            _txt(m, "admin_banned", "🚫 Banned {0}{1}.").format(user.mention, suffix)
        )

    try:
        await app.unban_chat_member(m.chat.id, user.id)
    except Exception as ex:
        return await m.reply_text(
            _txt(m, "admin_bot_no_rights", "Failed. Reason: <code>{0}</code>").format(
                type(ex).__name__
            )
        )
    await m.reply_text(
        _txt(m, "admin_unbanned", "✅ Unbanned {0}.").format(user.mention)
    )


@app.on_message(
    filters.command(["promote", "demote"]) & filters.group & ~app.bl_users
)
@lang.language()
@admin_check
async def _promote(_, m: types.Message):
    user = await _safe_extract_user(m)
    if not user:
        return await m.reply_text(m.lang["user_not_found"])

    if error := await _protected(m, user):
        return await m.reply_text(error)

    promote = m.command[0] == "promote"
    try:
        await app.promote_chat_member(
            m.chat.id,
            user.id,
            privileges=PROMOTE_RIGHTS if promote else DEMOTE_RIGHTS,
        )
    except Exception as ex:
        return await m.reply_text(
            _txt(m, "admin_bot_no_rights", "Failed. Reason: <code>{0}</code>").format(
                type(ex).__name__
            )
        )

    await db.get_admins(m.chat.id, reload=True)
    if promote:
        await m.reply_text(
            _txt(m, "admin_promoted", "⬆️ Promoted {0} to admin.").format(user.mention)
        )
    else:
        await m.reply_text(
            _txt(m, "admin_demoted", "⬇️ Demoted {0}.").format(user.mention)
        )


@app.on_message(
    filters.command(["fullpromote"]) & filters.group & ~app.bl_users
)
@lang.language()
@admin_check
async def _fullpromote(_, m: types.Message):
    """Full admin rights including can_promote_members."""
    user = await _safe_extract_user(m)
    if not user:
        return await m.reply_text(m.lang["user_not_found"])

    if error := await _protected(m, user):
        return await m.reply_text(error)

    try:
        await app.promote_chat_member(
            m.chat.id, user.id, privileges=FULLPROMOTE_RIGHTS
        )
    except Exception as ex:
        return await m.reply_text(
            _txt(m, "admin_bot_no_rights", "Failed. Reason: <code>{0}</code>").format(
                type(ex).__name__
            )
        )

    await db.get_admins(m.chat.id, reload=True)
    await m.reply_text(
        _txt(m, "admin_fullpromoted", "⏫ Fully promoted {0}.").format(user.mention)
    )


@app.on_message(filters.command(["kick"]) & filters.group & ~app.bl_users)
@lang.language()
@admin_check
async def _kick(_, m: types.Message):
    """Ban + immediate unban = kick."""
    user = await _safe_extract_user(m)
    if not user:
        return await m.reply_text(m.lang["user_not_found"])

    if error := await _protected(m, user):
        return await m.reply_text(error)
    if await is_admin(m.chat.id, user.id):
        return await m.reply_text(
            _txt(m, "admin_cant_admin", "You can't kick an admin.")
        )

    try:
        await app.ban_chat_member(m.chat.id, user.id)
        await app.unban_chat_member(m.chat.id, user.id)
    except Exception as ex:
        return await m.reply_text(
            _txt(m, "admin_bot_no_rights", "Failed. Reason: <code>{0}</code>").format(
                type(ex).__name__
            )
        )
    await m.reply_text(
        _txt(m, "admin_kicked", "👢 Kicked {0}.").format(user.mention)
    )

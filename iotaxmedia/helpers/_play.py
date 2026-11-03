# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import asyncio

from pyrogram import enums, errors, types

from iotaxmedia import app, config, db, logger, queue, yt
from iotaxmedia.helpers import utils


def normalize_invite_link(invite_link: str) -> str:
    if not invite_link:
        return invite_link
    if invite_link.startswith("https://t.me/+"):
        return invite_link.replace("https://t.me/+", "https://t.me/joinchat/", 1)
    if invite_link.startswith("http://t.me/+"):
        return invite_link.replace("http://t.me/+", "https://t.me/joinchat/", 1)
    if invite_link.startswith("t.me/+"):
        return "https://t.me/joinchat/" + invite_link.split("t.me/+", 1)[1]
    return invite_link


def _is_missing_member_error(exc: BaseException) -> bool:
    if isinstance(
        exc,
        (
            errors.UserNotParticipant,
            errors.PeerIdInvalid,
            errors.exceptions.bad_request_400.UserNotParticipant,
            errors.exceptions.bad_request_400.PeerIdInvalid,
        ),
    ):
        return True
    return type(exc).__name__ in {"UserNotParticipant", "PeerIdInvalid"}


async def _join_with_invite(bot, client, chat_id: int, invite_link: str) -> None:
    invite_link = normalize_invite_link(invite_link)
    try:
        await client.join_chat(invite_link)
        return
    except errors.UserAlreadyParticipant:
        return
    except errors.InviteHashExpired:
        fresh = normalize_invite_link(await bot.export_chat_invite_link(chat_id))
        await client.join_chat(fresh)
    except errors.InviteRequestSent:
        await asyncio.sleep(2)
        try:
            await bot.approve_chat_join_request(chat_id, client.id)
        except (errors.HideRequesterMissing, errors.UserAlreadyParticipant):
            pass


async def invite_assistant(bot, client, m: types.Message) -> bool:
    chat_id = m.chat.id
    bot_name = getattr(bot, "name", None) or getattr(app, "name", "assistant")
    umm = await m.reply_text(m.lang["play_invite"].format(bot_name))

    try:
        await bot.add_chat_members(chat_id, client.id)
    except errors.UserAlreadyParticipant:
        pass
    except Exception:
        invite_link = None
        if m.chat.username:
            invite_link = m.chat.username
            try:
                await client.resolve_peer(invite_link)
            except Exception:
                pass
        else:
            try:
                chat = await bot.get_chat(chat_id)
                invite_link = getattr(chat, "invite_link", None)
                if not invite_link:
                    invite_link = await bot.export_chat_invite_link(chat_id)
            except errors.ChatAdminRequired:
                await umm.edit_text(m.lang["admin_required"])
                return False
            except Exception as ex:
                await umm.edit_text(
                    m.lang["play_invite_error"].format(type(ex).__name__)
                )
                return False
        try:
            await asyncio.sleep(1)
            await _join_with_invite(bot, client, chat_id, invite_link)
        except errors.ChatAdminRequired:
            await umm.edit_text(m.lang["admin_required"])
            return False
        except Exception as ex:
            logger.error(f"Error joining chat - {chat_id}: {ex}")
            await umm.edit_text(m.lang["play_invite_error"].format(type(ex).__name__))
            return False

    try:
        await umm.delete()
    except Exception:
        pass
    try:
        await client.resolve_peer(chat_id)
    except Exception:
        try:
            await client.get_chat(chat_id)
        except Exception:
            pass
    return True


_PRESENT_STATUSES = {
    enums.ChatMemberStatus.MEMBER,
    enums.ChatMemberStatus.ADMINISTRATOR,
    enums.ChatMemberStatus.OWNER,
}
_BLOCKED_STATUSES = {
    enums.ChatMemberStatus.BANNED,
    enums.ChatMemberStatus.RESTRICTED,
}


def assistant_unban_markup(lang: dict) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(
        [
            [
                types.InlineKeyboardButton(
                    text=lang.get("play_unban_btn", "Unban Assistant"),
                    callback_data="unban_assistant",
                    style=enums.ButtonStyle.SUCCESS,
                )
            ]
        ]
    )


async def _reply_assistant_banned(bot, client, m: types.Message) -> None:
    await m.reply_text(
        m.lang["play_banned"].format(
            getattr(bot, "name", None) or getattr(app, "name", "bot"),
            client.id,
            getattr(client, "mention", None) or getattr(client, "name", client.id),
            f"@{client.username}" if getattr(client, "username", None) else None,
        ),
        reply_markup=assistant_unban_markup(m.lang),
    )


async def ensure_assistant_present(bot, client, m: types.Message) -> bool:
    chat_id = m.chat.id
    member = None
    try:
        member = await bot.get_chat_member(chat_id, client.id)
    except errors.ChatAdminRequired:
        await m.reply_text(m.lang["admin_required"])
        return False
    except Exception as exc:
        if _is_missing_member_error(exc):
            member = None
        else:
            logger.info(
                f"[play] assistant membership unknown for {client.id} in {chat_id}: {exc!r}"
            )
            member = None

    if member is not None:
        if member.status in _BLOCKED_STATUSES:
            await _reply_assistant_banned(bot, client, m)
            return False
        if member.status not in _PRESENT_STATUSES:
            member = None

    if member is None:
        return await invite_assistant(bot, client, m)
    try:
        await client.resolve_peer(chat_id)
    except Exception:
        try:
            await client.get_chat(chat_id)
        except Exception:
            pass
    return True


def checkUB(play):
    async def wrapper(_, m: types.Message, *args, **kwargs):
        if not m.from_user:
            return await m.reply_text(m.lang["play_user_invalid"])

        chat_id = m.chat.id
        if m.chat.type != enums.ChatType.SUPERGROUP:
            await m.reply_text(m.lang["play_chat_invalid"])
            return await app.leave_chat(chat_id)

        if not m.reply_to_message and (
            len(m.command) < 2 or (len(m.command) == 2 and m.command[1] == "-f")
        ):
            return await m.reply_text(m.lang["play_usage"])

        if len(queue.get_queue(chat_id)) >= config.QUEUE_LIMIT:
            return await m.reply_text(
                m.lang["play_queue_full"].format(config.QUEUE_LIMIT)
            )

        force = (
            kwargs.get("force")
            or m.command[0].endswith("force")
            or (len(m.command) > 1 and "-f" in m.command[1])
        )
        video = kwargs.get("video") or (m.command[0][0] == "v" and config.VIDEO_PLAY)
        url = kwargs.get("url") or utils.get_url(m)
        if url and yt.invalid(url):
            return await m.reply_text(
                m.lang["play_not_found"].format(config.SUPPORT_CHAT)
            )
        m3u8 = kwargs.get("m3u8") or (url and not yt.valid(url))

        play_mode = await db.get_play_mode(chat_id)
        if play_mode or force:
            adminlist = await db.get_admins(chat_id)
            if (
                m.from_user.id not in adminlist
                and not await db.is_auth(chat_id, m.from_user.id)
                and m.from_user.id not in app.sudoers
            ):
                return await m.reply_text(m.lang["play_admin"])

        if chat_id not in db.active_calls:
            client = await db.get_client(chat_id)
            if client is None:
                return await m.reply_text(
                    "No assistant account available. Music playback requires a valid SESSION."
                )
            from iotaxmedia.helpers._chat_owner import resolve_app

            bot = resolve_app(chat_id) or app
            if not await ensure_assistant_present(bot, client, m):
                return

        if await db.get_cmd_delete(chat_id):
            try:
                await m.delete()
            except Exception:
                pass

        return await play(_, m, force=force, m3u8=m3u8, video=video, url=url)

    return wrapper

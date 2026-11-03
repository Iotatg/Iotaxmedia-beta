# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Assistant userbot chatbot (Sep 2026).

Runs a second Iota persona on the assistant userbot account (SESSION1 /
self.one) so replies can come from the assistant's real-user-account
username in addition to the main bot. Same persona prompt, same AI
provider, same conversation history.

Anti-loop filters:
- skip messages from any bot (assistant itself, main bot, other bots)
- skip slash commands (commands belong to the main bot)
- per-user 2-second cooldown
- DM and group @mention / reply-to-assistant / "iota" word triggers (not "aisha")
"""
import logging
import re
import time

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from iotaxmedia import userbot

logger = logging.getLogger(__name__)

_cooldowns: dict[int, float] = {}
COOLDOWN_SECS = 2.0
_DIRECT_RE = re.compile(r"\biota\b", re.IGNORECASE)
_registered = False


def _strip_mention(text: str, my_username: str) -> str:
    """Strip @assistant_username only. Keep iota words so a
    bare 'iota' still has text for the AI (stripping them used to
    empty the prompt and silently skip group replies)."""
    if my_username:
        text = re.sub(re.escape(f"@{my_username}"), "", text, flags=re.IGNORECASE)
    return text.strip()


def _cached_me(client):
    me = getattr(client, "me", None)
    if me is None:
        return None
    uid = getattr(me, "id", None)
    if not isinstance(uid, int) or uid == 0:
        return None
    return me


async def _resolve_me(client):
    me = _cached_me(client)
    if me is not None:
        return me
    try:
        return await client.get_me()
    except Exception as e:
        logger.debug(f"assistant_chat get_me failed: {e}")
        return None


async def _should_handle(client, message: Message) -> bool:
    if not message.from_user:
        return False
    if message.from_user.is_self:
        return False
    if message.from_user.is_bot:
        return False
    if message.service or not message.text:
        return False

    if message.text.lstrip().startswith(("/", ".")):
        return False

    uid = message.from_user.id
    now = time.time()
    last = _cooldowns.get(uid, 0)
    if now - last < COOLDOWN_SECS:
        return False
    _cooldowns[uid] = now

    ctype = message.chat.type
    if ctype == ChatType.PRIVATE:
        return True

    me = await _resolve_me(client)
    my_username = ((me.username or "") if me else "").lower()
    my_id = me.id if me else 0
    if message.reply_to_message and message.reply_to_message.from_user:
        if my_id and message.reply_to_message.from_user.id == my_id:
            return True
    text_lower = (message.text or "").lower()
    if my_username and f"@{my_username}" in text_lower:
        return True
    if _DIRECT_RE.search(message.text or ""):
        return True
    return False


async def _run_chatbot(client, message: Message):
    from iotaxmedia.plugins.chatbot import _do_reply

    is_group = message.chat.type != ChatType.PRIVATE
    original = (message.text or "").strip()
    if is_group:
        me = await _resolve_me(client)
        uname = (me.username or "") if me else ""
        clean = _strip_mention(original, uname)
        user_text = clean or original
        if not user_text:
            return
    else:
        user_text = original

    await _do_reply(message, user_text, is_group=is_group)


async def _handle(client, message: Message):
    try:
        from iotaxmedia.plugins.chatbot import _ai_ready

        if not _ai_ready():
            return
        if not await _should_handle(client, message):
            return
        await _run_chatbot(client, message)
    except Exception as e:
        logger.warning(f"assistant_chat handler error: {e}")


def register():
    """Register the message handler on userbot.one. Called from __main__."""
    global _registered
    if _registered:
        return
    _registered = True

    if not getattr(userbot, "one", None):
        logger.info("assistant_chat: no userbot.one, skipping")
        return

    userbot.one.on_message(
        filters.text
        & ~filters.regex(r"^[/.]")
        & ~filters.bot
        & ~filters.service,
    )(_handle)
    logger.info("assistant_chat: registered on userbot.one (SESSION1)")

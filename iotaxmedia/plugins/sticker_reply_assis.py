# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""
Assistant userbot sticker-to-sticker reply (Sep 2026).

The assistant account (SESSION1 / userbot.one) replies to stickers it
sees in DMs and groups using the same mood engine as the main bot in
sticker_reply.py. Re-uses that module's helper functions and the
cooldown/anti-loop rules from assistant_chat so behaviour stays
consistent across main bot and assistant.

Trigger rules (mirrors assistant_chat._should_handle):
  - DMs: always (when a sticker arrives)
  - Groups: only when reply-to-assistant, or message contains a
    "@<assistant_username>" or the word "iota" (not "aisha")
  - Skip messages from any bot
  - Skip messages starting with "/" or "." (commands belong to main
    bot)
  - 2-second per-user cooldown
"""
import logging
import re
import time

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.types import Message

from iotaxmedia import userbot
from iotaxmedia.plugins.sticker_reply import (
    _auto_reply_from_pack,
    _detect_mood_from_sticker,
    _reply_any_sticker,
    _reply_sticker_for_mood,
)
from iotaxmedia.plugins.assistant_chat import (
    COOLDOWN_SECS,
    _cooldowns,
    _DIRECT_RE,
)

logger = logging.getLogger(__name__)

_registered = False


async def _should_handle_assistant(client, message: Message) -> bool:
    """Same gate as assistant_chat._should_handle plus a sticker check."""
    if not message.from_user:
        return False
    if message.from_user.is_self:
        return False
    if message.from_user.is_bot:
        return False
    if message.service:
        return False
    if not getattr(message, "sticker", None):
        return False
    text = (message.text or message.caption or "") or ""
    if text.lstrip().startswith(("/", ".")):
        return False

    uid = message.from_user.id
    now = time.time()
    last = _cooldowns.get(uid, 0)
    if now - last < COOLDOWN_SECS:
        return False
    _cooldowns[uid] = now

    if message.chat and message.chat.type == ChatType.PRIVATE:
        return True

    me = getattr(client, "me", None)
    uid = getattr(me, "id", None) if me is not None else None
    if not isinstance(uid, int) or uid == 0:
        try:
            me = await client.get_me()
        except Exception as e:
            logger.debug(f"assistant sticker: get_me failed: {e}")
            return False
        uid = getattr(me, "id", None) if me is not None else None
    my_id = uid if isinstance(uid, int) else 0
    my_username = ((me.username or "") if me else "").lower()

    if message.reply_to_message and message.reply_to_message.from_user:
        if my_id and message.reply_to_message.from_user.id == my_id:
            return True
    if my_username and f"@{my_username}" in text.lower():
        return True
    if text and _DIRECT_RE.search(text):
        return True
    return False


async def _handle_assistant_sticker(client, message: Message):
    try:
        if not await _should_handle_assistant(client, message):
            return
        mood = _detect_mood_from_sticker(message.sticker)
        if await _reply_sticker_for_mood(message, mood, client=client):
            return
        if await _auto_reply_from_pack(message, client=client):
            return
        await _reply_any_sticker(message, client=client)
    except Exception as e:
        logger.warning(f"assistant sticker handler error: {e}")


def register():
    """Attach the sticker handler to userbot.one. Called from __main__.

    No-op if SESSION1 is not configured (userbot.one is None).
    """
    global _registered
    if _registered:
        return
    _registered = True

    if not getattr(userbot, "one", None):
        logger.info("sticker_reply_assis: no userbot.one, skipping")
        return

    userbot.one.on_message(
        filters.sticker & ~filters.bot & ~filters.service,
    )(_handle_assistant_sticker)
    logger.info("sticker_reply_assis: registered on userbot.one (SESSION1)")

# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""
Iota Smart Sticker / GIF / Photo Reply System for iotaxmedia-beta.

Ported from IotaXMedia/plugins/tools/sticker_reply.py and
iota/handlers/sticker_reply.py with these iotaxmedia-beta-specific tweaks:

  * Uses `app.bl_users` filter (set of blacklisted user ids) instead of
    BANNED_USERS from config.
  * Lazy-imports `chatbot._chatbot_enabled` (and the per-clone
    customization lookup) so it stays decoupled at module load.
  * No GIF reaction (we keep photo-reaction for the main bot only) — the
    plan explicitly excluded GIFs in this iteration.
  * Owner cmds sit in filter group -3 so they fire before any later
    handler swallows the message. All responses go through `_safe_reply`
    with parse_mode=DISABLED and a 3-step fallback.

Public surface:

  sticker_reply_handler  sticker -> sticker
  photo_reaction_handler photo -> short cute reply
  emoji_only_handler     emoji-only DM -> emoji->sticker reply
  sticker_owner_router   /addsticker etc.  (owner/sudo only)
"""
import asyncio
import logging
import random
import re

from pyrogram import filters, raw
from pyrogram.enums import ChatAction, ChatType, ParseMode
from pyrogram.file_id import FileId, FileType
from pyrogram.types import Message

from iotaxmedia import app
from iotaxmedia.helpers.sticker_db import (
    add_sticker_to_pack,
    clear_sticker_pack,
    get_stickers_for_mood,
    list_all_sticker_packs,
)
from iotaxmedia import config as _config

logger = logging.getLogger(__name__)


_EMOJI_MOOD: dict = {
    "\U0001f602": "laugh", "\U0001f923": "laugh", "\U0001f639": "laugh", "\U0001f480": "laugh",
    "\U0001f60d": "love", "\U0001f970": "love", "\U0001f495": "love", "\U0001f49e": "love",
    "\u2764\ufe0f": "love", "\U0001faf6": "love", "\U0001f49d": "love", "\U0001f498": "love",
    "\U0001f62d": "sad", "\U0001f622": "sad", "\U0001f494": "sad", "\U0001f614": "sad", "\U0001f61e": "sad",
    "\U0001f621": "angry", "\U0001f92c": "angry", "\U0001f624": "angry", "\U0001f4a2": "angry",
    "\U0001f973": "happy", "\U0001f60a": "happy", "\U0001f601": "happy", "\U0001f389": "happy",
    "\U0001f604": "happy", "\U0001f929": "happy", "\U0001f38a": "happy",
    "\U0001f62e": "surprise", "\U0001f631": "surprise", "\U0001f632": "surprise", "\U0001f440": "surprise",
    "\U0001f483": "dance", "\U0001f57a": "dance", "\U0001f3b5": "dance", "\U0001f3b6": "dance",
    "\U0001f60e": "cool", "\U0001f919": "cool", "\u270c\ufe0f": "cool",
    "\U0001f97a": "cute", "\U0001f338": "cute", "\u2728": "cute", "\U0001f337": "cute",
    "\U0001f351": "cute", "\U0001f33c": "cute",
}


_MOOD_RELATED: dict = {
    "happy": ["laugh", "dance", "cute", "cool"],
    "laugh": ["happy", "cute", "dance"],
    "love": ["cute", "sad", "happy"],
    "cute": ["love", "happy", "laugh"],
    "sad": ["love", "cute"],
    "angry": ["cool", "surprise"],
    "surprise": ["cool", "angry"],
    "dance": ["happy", "cool", "laugh"],
    "cool": ["happy", "dance", "surprise"],
    "default": [],
}

_AUTO_SAVED_PACKS: dict = {}


def _detect_mood_from_sticker(sticker) -> str:
    if not sticker:
        return "default"
    emoji_str = getattr(sticker, "emoji", None) or ""


    for key, mood in _EMOJI_MOOD.items():
        if key in emoji_str:
            return mood
    for ch in emoji_str:
        m = _EMOJI_MOOD.get(ch)
        if m:
            return m
    return "default"


def _detect_mood_from_text(text: str) -> str:
    for key, mood in _EMOJI_MOOD.items():
        if key in (text or ""):
            return mood
    for ch in text or "":
        m = _EMOJI_MOOD.get(ch)
        if m:
            return m
    tl = (text or "").lower()
    if any(w in tl for w in ["dance", "vibe", "music", "song"]):
        return "dance"
    if any(w in tl for w in ["love", "kiss", "heart", "pyaar"]):
        return "love"
    if any(w in tl for w in ["funny", "lol", "haha", "laugh"]):
        return "laugh"
    if any(w in tl for w in ["angry", "mad", "rage", "gussa"]):
        return "angry"
    if any(w in tl for w in ["cute", "kawaii", "aww", "soft"]):
        return "cute"
    return "default"


def _sanitize_mood(text: str) -> str:
    slug = (text or "").strip().lower().replace(" ", "_")
    slug = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in slug)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "default"


def _doc_emoji(doc) -> str:
    """Emoji alt from a raw Document's sticker attribute."""
    for a in getattr(doc, "attributes", None) or []:
        if isinstance(a, raw.types.DocumentAttributeSticker):
            return getattr(a, "alt", None) or ""
        if isinstance(a, raw.types.DocumentAttributeCustomEmoji):
            return getattr(a, "alt", None) or ""
    return ""


def _doc_to_file_id(doc) -> str:
    """Encode a raw Document into a pyrogram sticker file_id string."""
    return FileId(
        file_type=FileType.STICKER,
        dc_id=doc.dc_id,
        media_id=doc.id,
        access_hash=doc.access_hash,
        file_reference=doc.file_reference or b"",
    ).encode()


def _auto_mood_from_pack(sticker_set) -> str:
    """
    Accepts either a high-level sticker set (.stickers with .emoji) or a
    raw messages.StickerSet (.documents with DocumentAttributeSticker.alt).
    """
    tally = {}
    stickers = getattr(sticker_set, "stickers", None) or []
    docs = getattr(sticker_set, "documents", None) or []
    for s in stickers:
        for ch in (getattr(s, "emoji", None) or ""):
            m = _EMOJI_MOOD.get(ch)
            if m:
                tally[m] = tally.get(m, 0) + 1
    for doc in docs:
        for ch in _doc_emoji(doc):
            m = _EMOJI_MOOD.get(ch)
            if m:
                tally[m] = tally.get(m, 0) + 1
    if tally:
        return max(tally, key=tally.get)
    set_obj = getattr(sticker_set, "set", None)
    title = (
        getattr(sticker_set, "title", None)
        or getattr(set_obj, "title", None)
        or ""
    )
    return _sanitize_mood(title)


def _pick_other(file_ids: list, current_fid: str) -> str:
    if not file_ids:
        return current_fid
    for fid in random.sample(file_ids, len(file_ids)):
        if fid != current_fid:
            return fid
    return file_ids[0]


def _is_reply_to_bot(message: Message) -> bool:
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return False
    return message.reply_to_message.from_user.id == app.id


def _is_tagged(text: str) -> bool:
    uname = (app.username or getattr(_config, "BOT_USERNAME", "") or "").lower()
    if not uname or not text:
        return False
    return f"@{uname}" in text.lower()


def _should_respond(message: Message) -> bool:
    """DMs always fire. Groups fire on @tag, reply-to-bot, or when
    /chatbot on has been toggled for that group (lazy import avoids a
    circular load on plugin import)."""
    if message.chat and message.chat.type == ChatType.PRIVATE:
        return True
    try:
        from iotaxmedia.plugins.chatbot import _chatbot_enabled
        if message.chat and message.chat.id in _chatbot_enabled:
            return True
    except Exception:
        pass
    caption = (message.caption or "") + (message.text or "")
    return _is_reply_to_bot(message) or _is_tagged(caption)


async def _choose_sticker(message: Message, client=None) -> None:
    try:
        bot = client or getattr(message, "_client", None) or app
        chat_id = message.chat.id if message.chat else 0
        if chat_id:
            await bot.send_chat_action(chat_id, ChatAction.CHOOSE_STICKER)
    except Exception:
        pass


async def _send_sticker_reply(message: Message, file_id: str, client=None) -> bool:
    bot = client or getattr(message, "_client", None)
    await _choose_sticker(message, client=bot)
    try:
        if bot is not None:
            await bot.send_sticker(
                message.chat.id,
                file_id,
                reply_to_message_id=message.id,
            )
            return True
        await message.reply_sticker(file_id)
        return True
    except Exception as e:
        logger.debug(f"Sticker send failed: {e}")
        return False


async def _reply_sticker_for_mood(message: Message, mood: str, client=None) -> bool:
    packs = await list_all_sticker_packs()
    candidates = [mood] + _MOOD_RELATED.get(mood, [])
    for m in candidates:
        if packs.get(m):
            try:
                sids = await get_stickers_for_mood(m)
            except Exception:
                sids = []
            if sids:
                if await _send_sticker_reply(message, random.choice(sids), client=client):
                    return True
                return False
    return False


async def _reply_any_sticker(message: Message, client=None) -> bool:
    packs = await list_all_sticker_packs()
    for m in packs:
        try:
            sids = await get_stickers_for_mood(m)
        except Exception:
            sids = []
        if sids:
            if await _send_sticker_reply(message, random.choice(sids), client=client):
                return True
            return False
    return False


async def _save_pack_background(sticker_set, mood: str, set_name: str) -> None:
    try:
        docs = list(getattr(sticker_set, "documents", None) or [])
        high_level = list(getattr(sticker_set, "stickers", None) or [])
        if docs:
            for doc in docs:
                try:
                    await add_sticker_to_pack(mood, _doc_to_file_id(doc), 0)
                except Exception as e:
                    logger.debug(f"auto-save sticker failed: {e}")
        else:
            for s in high_level:
                try:
                    await add_sticker_to_pack(mood, s.file_id, 0)
                except Exception as e:
                    logger.debug(f"auto-save sticker failed: {e}")
        _AUTO_SAVED_PACKS[set_name] = mood
    except Exception as e:
        logger.debug(f"auto-save pack '{set_name}' failed: {e}")


async def _fetch_sticker_set(set_name: str, client=None):
    bot = client or app
    try:
        return await bot.invoke(
            raw.functions.messages.GetStickerSet(
                stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
                hash=0,
            )
        )
    except Exception:
        pass
    try:
        return await bot.get_sticker_set(set_name)
    except Exception as e:
        logger.debug(f"auto-reply: couldn't fetch pack '{set_name}': {e}")
        return None


async def _auto_reply_from_pack(message: Message, client=None) -> bool:
    sticker = message.sticker
    if not sticker:
        return False
    set_name = getattr(sticker, "set_name", None)
    if not set_name:
        return False

    bot = client or getattr(message, "_client", None)

    cached_mood = _AUTO_SAVED_PACKS.get(set_name)
    if cached_mood:
        try:
            sids = await get_stickers_for_mood(cached_mood)
        except Exception:
            sids = []
        if sids:
            if await _send_sticker_reply(
                message, _pick_other(sids, sticker.file_id), client=bot
            ):
                return True

    sticker_set = await _fetch_sticker_set(set_name, client=bot)
    if sticker_set is None:
        return False

    mood = _auto_mood_from_pack(sticker_set)
    docs = list(getattr(sticker_set, "documents", None) or [])
    high_level = list(getattr(sticker_set, "stickers", None) or [])
    if docs:
        file_ids = []
        for doc in docs:
            try:
                file_ids.append(_doc_to_file_id(doc))
            except Exception:
                pass
    else:
        file_ids = [s.file_id for s in high_level]

    asyncio.create_task(_save_pack_background(sticker_set, mood, set_name))

    if len(file_ids) <= 1:
        incoming = sticker.file_id
        if incoming:
            try:
                await add_sticker_to_pack(mood, incoming, 0)
            except Exception:
                pass
        return False

    return await _send_sticker_reply(
        message, _pick_other(file_ids, sticker.file_id), client=bot
    )




@app.on_message(
    filters.sticker & ~app.bl_users & ~filters.service,
    group=2,
)
async def sticker_reply_handler(client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    if not _should_respond(message):
        return

    mood = _detect_mood_from_sticker(message.sticker)

    if await _reply_sticker_for_mood(message, mood, client=client):
        return
    if await _auto_reply_from_pack(message, client=client):
        return
    if await _reply_any_sticker(message, client=client):
        return




_PHOTO_FALLBACKS = [
    "nice pic",
    "waah",
    "cute hain ye",
    "oof",
    "okay okay",
    "wow",
]


@app.on_message(
    filters.photo & ~app.bl_users & ~filters.service,
    group=2,
)
async def photo_reaction_handler(client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    if not _should_respond(message):
        return
    await message.reply_text(random.choice(_PHOTO_FALLBACKS))




_EMOJI_ONLY_STRIP_RE = re.compile(
    r"[\s"
    r"\U0001F300-\U0001FAFF"
    r"\U0001F600-\U0001F64F"
    r"\U0001F680-\U0001F6FF"
    r"\U0001F1E0-\U0001F1FF"
    r"\u2600-\u26FF"
    r"\u2700-\u27BF"
    r"\uFE00-\uFE0F"
    r"\u200d"
    r"\u20E3"
    r"]+"
)


@app.on_message(
    filters.private
    & filters.text
    & ~filters.regex(r"^[/.]")
    & ~app.bl_users
    & ~filters.service,
    group=2,
)
async def emoji_only_handler(client, message: Message):
    if not message.from_user or message.from_user.is_bot:
        return
    text = (message.text or "").strip()
    if not text or text.startswith("/") or text.startswith("."):
        return
    stripped = _EMOJI_ONLY_STRIP_RE.sub("", text)
    if stripped:
        return
    mood = _detect_mood_from_text(text)
    await _reply_sticker_for_mood(message, mood, client=client)




def _is_owner_or_sudo(message: Message) -> bool:
    uid = message.from_user.id if message.from_user else 0
    if not uid:
        return False
    owner_id = getattr(_config, "OWNER_ID", 0)
    if owner_id and int(uid) == int(owner_id):
        return True
    try:
        sudo = set(getattr(_config, "SUDOERS", set()) or set())
    except Exception:
        sudo = set()
    if not sudo and getattr(app, "sudoers", None) is not None:
        try:
            for u in app.sudoers:
                sudo.add(int(u))
        except Exception:
            pass
    try:
        if int(uid) in sudo:
            return True
    except Exception:
        pass
    return False


async def _safe_reply(message: Message, text: str, client=None) -> None:
    """Always deliver a plain-text reply. Never raise to caller.

    3-step fallback: reply-to original -> bare send_message -> reply_text
    (no quote). Always parse_mode=DISABLED so stray markup never breaks us.
    """
    chat_id = message.chat.id if message.chat else 0
    bot = client or app
    plain = (
        text.replace("**", "")
        .replace("__", "")
        .replace("`", "")
        .replace("<", "")
        .replace(">", "")
    )
    try:
        m = await bot.send_message(
            chat_id, plain, parse_mode=ParseMode.DISABLED,
            reply_to_message_id=message.id,
        )
        logger.info(f"sticker_reply ok chat={chat_id} mid={getattr(m, 'id', '?')}")
        return
    except Exception as e1:
        logger.warning(f"send_message(reply) failed chat={chat_id}: {e1}")
    try:
        m = await bot.send_message(chat_id, plain, parse_mode=ParseMode.DISABLED)
        logger.info(f"sticker_reply bare ok chat={chat_id} mid={getattr(m, 'id', '?')}")
        return
    except Exception as e2:
        logger.exception(f"send_message bare failed chat={chat_id}: {e2}")
    try:
        await message.reply_text(plain, quote=False)
        logger.info(f"sticker_reply fallback ok chat={chat_id}")
    except Exception as e3:
        logger.exception(f"all reply paths failed chat={chat_id}: {e3}")


async def _deny_if_not_sudo(message: Message) -> bool:
    """Return True if denied (caller should return). Always sends a reply."""
    if _is_owner_or_sudo(message):
        return False
    uid = message.from_user.id if message.from_user else "?"
    await _safe_reply(
        message,
        f"Owner/sudo only.\nYour id: {uid}\nOwner id: {getattr(_config, 'OWNER_ID', '?')}",
    )
    return True


def _cmd_args(message: Message) -> list:
    if message.command and len(message.command) > 1:
        return list(message.command[1:])
    text = (message.text or message.caption or "").strip()
    if not text:
        return []
    parts = text.split()
    return parts[1:] if len(parts) > 1 else []


_STICKER_CMD_RE_LIST = [
    "addsticker", "addstickerpack", "addpack",
    "stickerpacks", "previewsticker", "clearstickers", "stickertest",
]
_STICKER_CMD_FILTER = (
    filters.command(_STICKER_CMD_RE_LIST, prefixes=["/", ".", "!"])
    | filters.regex(
        r"(?i)^[/!.](addsticker|addstickerpack|addpack|stickerpacks|previewsticker|clearstickers|stickertest)(@\w+)?(\s|$)"
    )
)


@app.on_message(_STICKER_CMD_FILTER, group=-3)
async def sticker_owner_router(client, message: Message):
    """Single early-group router so sticker pack cmds always fire, even if
    other handlers / command-filter edge cases would otherwise miss them.
    Runs at group=-3 (before group=0/1/2 handlers) so emoji_only_handler
    and chatbot never swallow the message first."""
    text = (message.text or message.caption or "").strip()
    uid = message.from_user.id if message.from_user else 0
    chat_id = message.chat.id if message.chat else 0
    logger.info(f"sticker_cmd hit uid={uid} chat={chat_id} text={text!r}")

    m = re.match(
        r"(?i)^[/!.](addstickerpack|addsticker|addpack|stickerpacks|previewsticker|clearstickers|stickertest)(?:@\w+)?(?:\s+(.*))?$",
        text,
        re.DOTALL,
    )
    if m:
        raw_cmd = m.group(1).lower()
        arg_str = (m.group(2) or "").strip()
        args = arg_str.split() if arg_str else []
    elif message.command:
        raw_cmd = (message.command[0] or "").lower()
        args = list(message.command[1:]) if len(message.command) > 1 else []
    else:
        raw_cmd, args = "", []

    logger.info(f"sticker_cmd parsed cmd={raw_cmd!r} args={args!r} sudo={_is_owner_or_sudo(message)}")

    if raw_cmd == "stickertest":
        packs = {}
        try:
            packs = await list_all_sticker_packs()
        except Exception as e:
            packs = {"error": str(e)}
        await _safe_reply(
            message,
            f"Sticker system OK.\nYour id: {uid}\nOwner: {getattr(_config, 'OWNER_ID', '?')}\n"
            f"Sudo: {_is_owner_or_sudo(message)}\nChat: {chat_id}\n"
            f"Packs: {packs or '{}'}",
            client=client,
        )
        return

    if not _is_owner_or_sudo(message):
        await _safe_reply(
            message,
            f"Owner/sudo only.\nYour id: {uid}\nOwner id: {getattr(_config, 'OWNER_ID', '?')}",
            client=client,
        )
        return

    try:
        if raw_cmd == "addsticker":
            await _do_addsticker(message, args, client)
        elif raw_cmd in ("addstickerpack", "addpack"):
            await _do_addpack(
                message, args, client, force_auto=(raw_cmd == "addpack" or not args)
            )
        elif raw_cmd == "stickerpacks":
            await _do_stickerpacks(message, client)
        elif raw_cmd == "previewsticker":
            await _do_previewsticker(message, args, client)
        elif raw_cmd == "clearstickers":
            await _do_clearstickers(message, args, client)
        else:
            await _safe_reply(
                message, f"Unknown sticker cmd: {raw_cmd or text}", client=client
            )
    except Exception as e:
        logger.exception(f"sticker cmd {raw_cmd} crashed")
        await _safe_reply(message, f"Error in /{raw_cmd}: {e}", client=client)


async def _do_addsticker(message: Message, args: list, client=None):
    reply = message.reply_to_message
    if not reply or not getattr(reply, "sticker", None):
        return await _safe_reply(
            message,
            "Add a reply sticker\n\n"
            "1. Send / forward a sticker to this chat\n"
            "2. REPLY to that sticker with:\n"
            "   /addsticker happy\n"
            "   /addsticker   (auto mood from emoji)\n\n"
            "Moods: happy, sad, love, laugh, angry, cute, dance, cool, surprise\n\n"
            "Whole pack: /addpack  or  /addstickerpack happy\n"
            "List: /stickerpacks",
            client=client,
        )
    if args:
        mood = _sanitize_mood(args[0])
        auto = False
    else:
        mood = _detect_mood_from_sticker(reply.sticker)
        auto = True
    fid = reply.sticker.file_id
    await add_sticker_to_pack(
        mood, fid, message.from_user.id if message.from_user else 0
    )
    count = len(await get_stickers_for_mood(mood))
    extra = " (mood auto-detected)" if auto else ""
    logger.info(f"addsticker mood={mood} count={count} auto={auto}")
    await _safe_reply(
        message,
        f"Sticker added to {mood} pack! ({count} total){extra}",
        client=client,
    )


async def _do_addpack(message: Message, args: list, client=None, force_auto: bool = False):
    reply = message.reply_to_message
    if not reply or not getattr(reply, "sticker", None):
        return await _safe_reply(
            message,
            "Import a whole sticker pack\n\n"
            "Reply to any sticker from the pack with:\n"
            "/addpack - auto mood\n"
            "/addstickerpack happy - pick mood",
            client=client,
        )
    sticker = reply.sticker
    set_name = getattr(sticker, "set_name", None)
    if not set_name:
        return await _safe_reply(
            message,
            "That sticker has no pack name. Use /addsticker for a single sticker.",
            client=client,
        )
    await _safe_reply(message, f"Fetching pack {set_name}...", client=client)
    bot = client or app
    try:
        sticker_set = await bot.invoke(
            raw.functions.messages.GetStickerSet(
                stickerset=raw.types.InputStickerSetShortName(short_name=set_name),
                hash=0,
            )
        )
    except Exception as e:
        logger.exception(f"GetStickerSet failed for {set_name}")
        return await _safe_reply(message, f"Couldn't fetch pack: {e}", client=client)

    if force_auto or not args:
        mood = _auto_mood_from_pack(sticker_set)
        auto = True
    else:
        mood = _sanitize_mood(args[0])
        auto = False

    added = 0
    uid = message.from_user.id if message.from_user else 0
    docs = list(getattr(sticker_set, "documents", None) or [])
    high_level = list(getattr(sticker_set, "stickers", None) or [])
    if docs:
        for doc in docs:
            try:
                fid = _doc_to_file_id(doc)
                await add_sticker_to_pack(mood, fid, uid)
                added += 1
            except Exception as e:
                logger.debug(f"add pack sticker failed: {e}")
    else:
        for s in high_level:
            try:
                await add_sticker_to_pack(mood, s.file_id, uid)
                added += 1
            except Exception as e:
                logger.debug(f"add pack sticker failed: {e}")

    total = len(await get_stickers_for_mood(mood))
    extra = " (mood auto-detected)" if auto else ""
    logger.info(f"addpack mood={mood} added={added} total={total} docs={len(docs)}")
    await _safe_reply(
        message,
        f"Imported {added} stickers from {set_name} into {mood}{extra}\n"
        f"({total} total in this pack)\n\n"
        f"/previewsticker {mood}  |  /stickerpacks",
        client=client,
    )


async def _do_stickerpacks(message: Message, client=None):
    packs = await list_all_sticker_packs()
    logger.info(f"stickerpacks count={len(packs)} data={packs}")
    if not packs:
        return await _safe_reply(
            message,
            "No sticker packs yet.\n\n"
            "Reply to a sticker with /addsticker happy\n"
            "or /addpack to import a whole pack.",
            client=client,
        )
    lines = [
        f"- {m}: {c} sticker{'s' if c != 1 else ''}"
        for m, c in sorted(packs.items())
    ]
    await _safe_reply(
        message,
        f"Sticker Packs ({len(packs)} moods)\n\n"
        + "\n".join(lines)
        + "\n\n/previewsticker <mood>\n/clearstickers <mood>",
        client=client,
    )


async def _do_previewsticker(message: Message, args: list, client=None):
    if not args:
        return await _safe_reply(
            message, "Usage: /previewsticker <mood>", client=client
        )
    mood = _sanitize_mood(args[0])
    stickers = await get_stickers_for_mood(mood)
    if not stickers:
        return await _safe_reply(
            message, f"No stickers in {mood} pack yet.", client=client
        )
    bot = client or app
    try:
        await bot.send_sticker(message.chat.id, random.choice(stickers))
        await _safe_reply(
            message, f"One of {len(stickers)} in {mood}", client=client
        )
    except Exception as e:
        await _safe_reply(
            message, f"Send failed (stale file_id?): {e}", client=client
        )


async def _do_clearstickers(message: Message, args: list, client=None):
    if not args:
        return await _safe_reply(
            message, "Usage: /clearstickers <mood>", client=client
        )
    mood = _sanitize_mood(args[0])
    n = await clear_sticker_pack(mood)
    await _safe_reply(
        message, f"Cleared {mood} pack ({n} stickers removed).", client=client
    )

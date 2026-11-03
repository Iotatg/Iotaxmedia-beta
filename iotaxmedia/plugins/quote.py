# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT























from io import BytesIO
import asyncio
import random
import re
import time

from bson import ObjectId
from httpx import AsyncClient, Timeout
from pyrogram import enums, filters
from pyrogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    InlineQueryResultArticle, InputTextMessageContent,
)

from iotaxmedia import app, db
from iotaxmedia.helpers import admin_check

QUOTE_API = "https://quote-api-p0px.onrender.com/generate.webp"


RAW = db.db

fetch = AsyncClient(
    http2=True,
    verify=False,
    headers={
        "Accept-Language": "id-ID",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/107.0.0.0 Safari/537.36 Edge/107.0.1418.42",
    },
    timeout=Timeout(40),
)



async def _group_settings(cid: int) -> dict:
    doc = await RAW.quote_groups.find_one({"_id": cid}) or {}
    return doc.get("settings", {}) or {}


async def _set_group_setting(cid: int, key: str, value):
    await RAW.quote_groups.update_one(
        {"_id": cid}, {"$set": {f"settings.{key}": value}}, upsert=True)


async def _inc_counter(cid: int) -> int:
    res = await RAW.quote_groups.find_one_and_update(
        {"_id": cid}, {"$inc": {"quoteCounter": 1}},
        upsert=True, return_document=True)
    return res.get("quoteCounter", 1)



async def _sender(m):
    if getattr(m, "forward_date", None) or getattr(m, "forward_origin", None):
        if getattr(m, "forward_from", None):
            return m.forward_from
        if getattr(m, "forward_from_chat", None):
            return m.forward_from_chat
        if getattr(m, "forward_sender_name", None):
            return type("S", (), {"id": abs(hash(m.forward_sender_name)) % (10 ** 8),
                                  "first_name": m.forward_sender_name,
                                  "last_name": "", "username": None,
                                  "title": m.forward_sender_name})()
        return type("S", (), {"id": 1, "first_name": "Someone",
                              "last_name": "", "username": None,
                              "title": "Someone"})()
    if getattr(m, "from_user", None):
        return m.from_user
    if getattr(m, "sender_chat", None):
        return m.sender_chat
    return type("S", (), {"id": 1, "first_name": "Someone",
                          "last_name": "", "username": None,
                          "title": "Someone"})()


def _ent(m):
    ents = getattr(m, "entities", None) or getattr(m, "caption_entities", None) or []
    out = []
    for e in ents:
        try:
            t = e.type.value.lower()
        except Exception:
            t = str(getattr(e, "type", "")).lower()
        out.append({"type": t, "offset": e.offset, "length": e.length})
    return out


def _text(m):
    return getattr(m, "text", None) or getattr(m, "caption", None) or ""


async def _build_payload(messages, include_reply, color, emojibrand, scale):
    payload = {
        "type": "quote", "format": "webp", "backgroundColor": color,
        "width": 512, "height": 768, "scale": scale,
        "emojiBrand": emojibrand, "messages": [],
    }
    for m in messages:
        s = await _sender(m)
        chat_type = "private"
        if getattr(m, "chat", None) and getattr(m.chat, "type", None):
            chat_type = str(m.chat.type).lower()
        name = (getattr(s, "first_name", "") or getattr(s, "title", "")
                or getattr(s, "username", "") or "Someone")
        if getattr(s, "last_name", None):
            name = f"{name} {s.last_name}"
        entry = {
            "entities": _ent(m),
            "chatId": getattr(s, "id", 1),
            "text": _text(m),
            "avatar": True,
            "from": {
                "id": getattr(s, "id", 1),
                "name": name,
                "username": getattr(s, "username", None) or "",
                "type": chat_type,
            },
        }
        reply = getattr(m, "reply_to_message", None)
        if include_reply and reply is not None:
            rs = await _sender(reply)
            rname = (getattr(rs, "first_name", "") or getattr(rs, "title", "")
                     or "Someone")
            if getattr(rs, "last_name", None):
                rname = f"{rname} {rs.last_name}"
            entry["replyMessage"] = {
                "name": rname, "text": _text(reply),
                "chatId": getattr(rs, "id", 1)}
        else:
            entry["replyMessage"] = {}
        payload["messages"].append(entry)
    return payload


async def _render(payload) -> bytes:


    for attempt in range(3):
        if attempt:
            await asyncio.sleep(2 * (attempt + 1))
        r = await fetch.post(QUOTE_API, json=payload)
        if r.status_code == 200:
            return r.content
        if r.status_code in (404, 502, 503) and attempt < 2:
            continue
        raise RuntimeError(f"quote-api HTTP {r.status_code}")



@app.on_message(filters.command("q") & filters.reply)
async def quote_cmd(client, message):
    args = message.text.split()[1:]
    flag = {"reply": False, "png": False, "img": False, "rate": False,
            "hidden": False, "media": False, "scale": None, "color": None}
    count = 1
    for a in args:
        if a in ("r", "reply"):
            flag["reply"] = True
        elif a in ("p", "png"):
            flag["png"] = True
        elif a in ("i", "img"):
            flag["img"] = True
        elif a == "rate":
            flag["rate"] = True
        elif a in ("h", "hidden"):
            flag["hidden"] = True
        elif a in ("m", "media"):
            flag["media"] = True
        elif re.match(r"s[+-]?\d*\.?\d+", a):
            flag["scale"] = float(a[1:])
        elif a.isdigit():
            count = int(a)
        elif a not in ("c", "crop"):
            flag["color"] = a
    count = max(1, min(count, 50))

    cid = message.chat.id
    settings = await _group_settings(cid)
    color = flag["color"] or settings.get("backgroundColor") or "//#292232"
    emojibrand = settings.get("emojiBrand") or "apple"
    scale = flag["scale"] or 2

    msgs = [message.reply_to_message]
    if count > 1:
        try:
            ids = list(range(message.reply_to_message.id,
                              message.reply_to_message.id + count))
            fetched = await client.get_messages(cid, ids)
            msgs = [m for m in fetched if m and not m.empty]
        except Exception:
            pass

    await message.reply_chat_action(enums.ChatAction.CHOOSE_STICKER)
    payload = await _build_payload(msgs, flag["reply"], color, emojibrand, scale)
    try:
        img = await _render(payload)
    except Exception as e:
        return await message.reply_text(f"Quote generate fail: {e}")
    buf = BytesIO(img)
    buf.name = "quote.webp"
    try:
        sent = await message.reply_sticker(buf, quote=True)
    except Exception:
        buf.seek(0)
        sent = await message.reply_document(
            buf, quote=True, file_name="quote.webp",
            caption="Sent as a file (sticker size limit exceeded).")

    try:
        local_id = await _inc_counter(cid)
        st = getattr(sent, "sticker", None)
        if st:
            await RAW.quote_quotes.insert_one({
                "_id": ObjectId(),
                "group_id": cid, "local_id": local_id,
                "file_id": st.file_id, "file_unique_id": st.file_unique_id,
                "up": 0, "down": 0, "created_at": time.time(),
                "rate_enabled": flag["rate"] or bool(settings.get("rate")),
                "text": _text(message.reply_to_message),
            })
    except Exception:
        pass

    if flag["rate"] or settings.get("rate"):
        try:
            await sent.edit_reply_markup(
                InlineKeyboardMarkup([[
                    InlineKeyboardButton(
                        "rate:up",
                        callback_data=f"rate:up:{sent.sticker.file_unique_id}"),
                    InlineKeyboardButton(
                        "rate:down",
                        callback_data=f"rate:down:{sent.sticker.file_unique_id}"),
                ]]))
        except Exception:
            pass


@app.on_message(filters.command("qtop") & filters.group)
async def qtop_cmd(client, message):
    docs = await RAW.quote_quotes.find(
        {"group_id": message.chat.id}).sort(
        [("up", -1), ("down", 1)]).limit(5).to_list(5)
    if not docs:
        return await message.reply_text("No quotes stored in this group yet.")
    for d in docs:
        score = d.get("up", 0) - d.get("down", 0)
        try:
            await message.reply_sticker(
                d["file_id"],
                caption=f"score {score} ({d.get('up',0)} up / {d.get('down',0)} down)")
        except Exception:
            pass


@app.on_message(filters.command("qrand") & filters.group)
async def qrand_cmd(client, message):
    docs = await RAW.quote_quotes.find(
        {"group_id": message.chat.id}).to_list(200)
    if not docs:
        return await message.reply_text("No quotes stored in this group yet.")
    d = random.choice(docs)
    try:
        await message.reply_sticker(d["file_id"])
    except Exception:
        await message.reply_text("Couldn't send a random quote.")


@app.on_message(filters.command("qcolor") & filters.group)
@admin_check
async def qcolor_cmd(client, message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Usage: /qcolor <#hex|random|transparent>")
    val = parts[1].strip()
    if val == "random":
        val = "#%06x" % random.randint(0, 0xFFFFFF)
    await _set_group_setting(message.chat.id, "backgroundColor", val)
    await message.reply_text(
        f"Default quote color set to <code>{val}</code>", parse_mode="html")


@app.on_message(filters.command("qb") & filters.group)
@admin_check
async def qb_cmd(client, message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Usage: /qb <apple|google|twitter|...>")
    brand = parts[1].strip().lower()
    await _set_group_setting(message.chat.id, "emojiBrand", brand)
    await message.reply_text(
        f"Emoji brand set to <code>{brand}</code>", parse_mode="html")


@app.on_message(filters.command("qemoji") & filters.group)
@admin_check
async def qemoji_cmd(client, message):
    parts = message.text.split(None, 1)
    on = (parts[1].strip().lower() if len(parts) > 1 else "on") in ("on", "1", "true", "yes")
    await _set_group_setting(message.chat.id, "emojiSuffix", "" if not on else "random")
    await message.reply_text(f"Emoji suffix {'on' if on else 'off'}.")


@app.on_message(filters.command("qgab") & filters.group)
@admin_check
async def qgab_cmd(client, message):
    parts = message.text.split(None, 1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        return await message.reply_text("Usage: /qgab <1-100> (random quote frequency)")
    n = max(1, min(int(parts[1].strip()), 100))
    await _set_group_setting(message.chat.id, "gab", n)
    await message.reply_text(f"Random quote gab set to 1/{n}.")


@app.on_message(filters.command("qrate") & filters.group)
@admin_check
async def qrate_cmd(client, message):
    parts = message.text.split(None, 1)
    on = (parts[1].strip().lower() if len(parts) > 1 else "on") in ("on", "1", "true", "yes")
    await _set_group_setting(message.chat.id, "rate", on)
    await message.reply_text(f"Quote rating {'enabled' if on else 'disabled'}.")


@app.on_message(filters.command("hidden") & filters.group)
@admin_check
async def hidden_cmd(client, message):
    parts = message.text.split(None, 1)
    on = (parts[1].strip().lower() if len(parts) > 1 else "on") in ("on", "1", "true", "yes")
    await _set_group_setting(message.chat.id, "hidden", on)
    await message.reply_text(f"Hidden (anonymous) quotes {'on' if on else 'off'}.")


@app.on_message(filters.command("privacy") & filters.group)
@admin_check
async def privacy_cmd(client, message):
    parts = message.text.split(None, 1)
    on = (parts[1].strip().lower() if len(parts) > 1 else "on") in ("on", "1", "true", "yes")
    await _set_group_setting(message.chat.id, "privacy", on)
    await message.reply_text(f"Privacy mode {'on' if on else 'off'}.")


@app.on_message(filters.command("qarchive") & filters.group)
@admin_check
async def qarchive_cmd(client, message):
    parts = message.text.split(None, 1)
    on = (parts[1].strip().lower() if len(parts) > 1 else "on") in ("on", "1", "true", "yes")
    await _set_group_setting(message.chat.id, "archive", on)
    await message.reply_text(f"Quote archive {'enabled' if on else 'disabled'}.")


@app.on_message(filters.command("qforget") & filters.group)
async def qforget_cmd(client, message):
    await RAW.quote_quotes.delete_many({"group_id": message.chat.id})
    await RAW.quote_groups.delete_one({"_id": message.chat.id})
    await message.reply_text("Forgot all quote data for this group.")


@app.on_message(filters.command("app"))
async def app_cmd(client, message):
    me = await client.get_me()
    await message.reply_text(
        "<b>QuotLyBot</b>\n\n"
        f"Bot: @{me.username}\n"
        "Reply to a message with /q to make a quote sticker.\n"
        "Use /qtop and /qrand in groups for the best quotes.",
        parse_mode="html")





@app.on_message(filters.command("qs") & filters.reply)
async def qs_cmd(client, message):
    st = message.reply_to_message.sticker if message.reply_to_message else None
    if not st:
        return await message.reply_text(
            "Reply to a quote sticker (made with /q) to save it.")
    try:
        data = (await st.download(in_memory=True)).getvalue()
        buf = BytesIO(data)
        buf.name = "quote.webp"
        await message.reply_sticker(buf)
        await message.reply_text(
            "Long-press the sticker -> Add to stickers to keep it in a pack.")
    except Exception as e:
        await message.reply_text(f"Couldn't save this sticker: {e}")


@app.on_message(filters.command("qd") & filters.group)
@admin_check
async def qd_cmd(client, message):
    parts = message.text.split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Usage: /qd <quote_local_id>")
    try:
        lid = int(parts[1].strip())
    except ValueError:
        return await message.reply_text("Invalid id.")
    doc = await RAW.quote_quotes.find_one(
        {"group_id": message.chat.id, "local_id": lid})
    if not doc:
        return await message.reply_text("Quote not found.")
    try:
        await client.delete_sticker_from_set(doc["file_id"])
    except Exception:
        pass
    await RAW.quote_quotes.delete_one({"_id": doc["_id"]})
    await message.reply_text("Quote deleted.")


@app.on_message(filters.command("qdrand") & filters.group)
@admin_check
async def qdrand_cmd(client, message):
    docs = await RAW.quote_quotes.find(
        {"group_id": message.chat.id}).to_list(200)
    if not docs:
        return await message.reply_text("No quotes stored.")
    d = random.choice(docs)
    try:
        await client.delete_sticker_from_set(d["file_id"])
    except Exception:
        pass
    await RAW.quote_quotes.delete_one({"_id": d["_id"]})
    await message.reply_text("Random quote deleted.")



@app.on_callback_query(filters.regex(r"^rate:(up|down):(.+)"))
async def rate_cb(client, query):
    _, vote, unique = query.data.split(":", 2)
    doc = await RAW.quote_quotes.find_one({"file_unique_id": unique})
    if not doc:
        return await query.answer("Quote not found.", show_alert=True)
    field = "up" if vote == "up" else "down"
    await RAW.quote_quotes.update_one({"_id": doc["_id"]}, {"$inc": {field: 1}})
    up = doc.get("up", 0) + (1 if vote == "up" else 0)
    down = doc.get("down", 0) + (1 if vote == "down" else 0)
    try:
        await query.message.edit_caption(
            f"score {up - down} ({up} up / {down} down)")
    except Exception:
        pass
    await query.answer("Voted!")



@app.on_inline_query()
async def quote_inline(client, inline):
    q = (inline.query or "").strip()
    if not q:
        return await inline.answer([], cache_time=1)
    fake = type("M", (), {})()
    fake.text = q
    fake.entities = []
    fake.caption = None
    fake.caption_entities = None
    fake.chat = type("C", (), {"type": "private"})()
    fake.from_user = inline.from_user
    fake.forward_from = None
    fake.forward_from_chat = None
    fake.forward_sender_name = None
    fake.forward_origin = None
    fake.forward_date = None
    fake.sender_chat = None
    fake.reply_to_message = None
    try:
        payload = await _build_payload([fake], False, "//#292232", "apple", 2)
        await _render(payload)
        results = [InlineQueryResultArticle(
            id="quote1",
            title="Quote this text",
            description=q[:60],
            input_message_content=InputTextMessageContent(q[:4000]),
        )]
        await inline.answer(results, cache_time=1)
    except Exception:
        await inline.answer([], cache_time=1)

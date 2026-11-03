# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Clone fleet management (MAIN bot only — excluded from clone boots).

Commands (private chat):
- /clone <token>        add + start a clone bot            (anyone)
- /delclone, /rmbot     stop + delete a clone              (owner of it or OWNER_ID)
- /myclone, /mybot      show your clone status             (anyone)
- /cloned, /totalbots   list all clones                    (OWNER_ID)
- /clonedinfo           details for one clone              (OWNER_ID)
- /delallclone          wipe every clone                   (OWNER_ID, confirmed)
"""

from pyrogram import filters, types

from iotaxmedia import app, config
from iotaxmedia.clone.runtime import get_manager, get_store, validate_token


def _owner_gate(m: types.Message) -> bool:
    return bool(m.from_user and m.from_user.id == config.OWNER_ID)


def _owner_filter():
    from pyrogram import filters as _f

    return _f.user(config.OWNER_ID)


def _bot_id(token: str) -> str:
    """The bot ID is simply the numeric prefix of its BotFather token."""
    return token.split(":", 1)[0]


async def _resolve_clone(query: str):
    """Find a clone registry doc by full token OR by its numeric bot ID."""
    query = query.strip()
    doc = await get_store().get_clone(query)
    if doc:
        return doc
    if not query.isdigit():
        return None
    docs = await get_store().all_clones()
    exact = [d for d in docs if _bot_id(d["_id"]) == query]
    if exact:
        return exact[0]

    prefixed = [d for d in docs if _bot_id(d["_id"]).startswith(query)]
    return prefixed[0] if len(prefixed) == 1 else None


@app.on_message(filters.private & filters.command(["clone"]))
async def _clone_add(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text(
            "**❍ ᴜsᴀɢᴇ »** /clone <bot_token>\n\n"
            "➥ ɢᴇᴛ ᴀ ᴛᴏᴋᴇɴ ꜰʀᴏᴍ @BotFather, ᴛʜᴇɴ ᴘᴀꜱᴛᴇ ɪᴛ ʜᴇʀᴇ ✔"
        )
    token = m.command[1].strip()
    if not validate_token(token):
        return await m.reply_text("**❌ ɪɴᴠᴀʟɪᴅ ᴛᴏᴋᴇɴ ꜰᴏʀᴍᴀᴛ ✘**")
    store = get_store()
    existing = await store.get_clone(token)
    if existing and existing.get("status") == "active":
        return await m.reply_text("**❍ ᴛʜɪꜱ ᴄʟᴏɴᴇ ᴀʟʀᴇᴀᴅʏ ᴇxɪꜱᴛꜱ ᴀɴᴅ ɪꜱ ᴀᴄᴛɪᴠᴇ ✔**")
    sent = await m.reply_text("**❍ ꜱᴛᴀʀᴛɪɴɢ ʏᴏᴜʀ ᴄʟᴏɴᴇ... ⏳**")
    try:
        ok = await get_manager().start_clone(token, m.from_user.id)
    except Exception as e:
        ok = False
        await sent.edit_text(f"**❌ ꜱᴛᴀʀᴛ ꜰᴀɪʟᴇᴅ ✘**\n➥ `{e}`")
        return
    if not ok:
        await sent.edit_text(
            "**❌ ᴄʟᴏɴᴇ ꜱᴛᴀʀᴛ ꜰᴀɪʟᴇᴅ ✘ (ᴄʜᴇᴄᴋ ɪᴛꜱ ʟᴏɢꜱ).\n➥ ɴᴏ ᴄʜᴀɴɢᴇꜱ ᴡᴇʀᴇ ᴋᴇᴘᴛ.**"
        )
        return
    uname = ""
    clone = get_manager().get_clone(token)
    try:
        uname = f"@{clone.app.username}" if clone and clone.app else ""
    except Exception:
        pass
    await sent.edit_text(
        f"**✅ ᴄʟᴏɴᴇ ꜱᴛᴀʀᴛᴇᴅ {uname} 🎉**\n\n"
        f"➥ ᴏᴡɴᴇʀ » `{m.from_user.id}`\n"
        "➥ ᴄᴜꜱᴛᴏᴍɪᴢᴇ ɪᴛ ꜰʀᴏᴍ ɪᴛꜱ ᴏᴡɴ ᴄʜᴀᴛ » /setstart, /setpingpic, /name …\n"
        "➥ ʀᴇᴍᴏᴠᴇ ᴀɴʏᴛɪᴍᴇ » /delclone"
    )


@app.on_message(filters.private & filters.command(["delclone", "rmbot"]))
async def _clone_del(_, m: types.Message):
    if not (m.from_user and (m.from_user.id in app.sudoers or _owner_gate(m))):
        return
    if len(m.command) < 2:
        return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /delclone <bot_id ya bot_token>")
    record = await _resolve_clone(m.command[1])
    if not record or record.get("status") == "deleted":
        return await m.reply_text("**❌ ᴜɴᴋɴᴏᴡɴ ᴄʟᴏɴᴇ ✘**")
    if (
        int(record.get("owner_id") or 0) != m.from_user.id
        and not _owner_gate(m)
    ):
        return await m.reply_text("**❌ ʏᴏᴜ ᴄᴀɴ ᴏɴʟʏ ᴅᴇʟᴇᴛᴇ ʏᴏᴜʀ ᴏᴡɴ ᴄʟᴏɴᴇ ✘**")
    await get_manager().delete_clone(record["_id"])
    await m.reply_text("**✅ ᴄʟᴏɴᴇ ᴅᴇʟᴇᴛᴇᴅ ✔**")


@app.on_message(filters.private & filters.command(["myclone", "mybot"]))
async def _my_clone(_, m: types.Message):
    docs = await get_store().clones_for_owner(m.from_user.id)
    if not docs:
        return await m.reply_text("**❍ ʏᴏᴜ ʜᴀᴠᴇ ɴᴏ ᴄʟᴏɴᴇ.\n➥ ᴀᴅᴅ ᴏɴᴇ ᴡɪᴛʜ » /clone <token>**")
    lines = []
    for d in docs:
        running = get_manager().get_clone(d["_id"])
        state = "running" if running and running.is_running() else d["status"]
        lines.append(f"➥ `{_bot_id(d['_id'])}` » {state}")
    await m.reply_text("**❍ ʏᴏᴜʀ ʙᴏᴛꜱ**\n\n" + "\n".join(lines))


@app.on_message(filters.private & filters.command(["cloned", "totalbots"]) & _owner_filter())
async def _cloned_list(_, m: types.Message):
    docs = [
        d
        for d in await get_store().all_clones()
        if d.get("status") != "deleted"
    ]
    mgr = get_manager()
    body = "\n".join(
        f"➥ `{_bot_id(d['_id'])}` » ᴏᴡɴᴇʀ {d.get('owner_id')} "
        f"{'🟢' if (c := mgr.get_clone(d['_id'])) and c.is_running() else '⚪'}"
        for d in docs
    )
    await m.reply_text(f"**❍ ᴛᴏᴛᴀʟ ʙᴏᴛꜱ » {len(docs)}**\n\n{body or '—'}")


@app.on_message(filters.private & filters.command(["clonedinfo"]) & _owner_filter())
async def _cloned_info(_, m: types.Message):
    if len(m.command) < 2:
        return await m.reply_text("**❍ ᴜꜱᴀɢᴇ »** /clonedinfo <bot_id ya bot_token>")
    d = await _resolve_clone(m.command[1])
    if not d or d.get("status") == "deleted":
        return await m.reply_text("**❌ ᴜɴᴋɴᴏᴡɴ ᴄʟᴏɴᴇ ✘**")
    c = get_manager().get_clone(d["_id"])
    extra = ""
    if c and c.app and getattr(c.app, "me", None):
        extra = f"\n➥ ᴀꜱ » @{c.app.username}"
    await m.reply_text(
        f"**❍ ᴄʟᴏɴᴇ ɪɴꜰᴏ »** `{_bot_id(d['_id'])}`\n\n"
        f"➥ ᴏᴡɴᴇʀ » `{d.get('owner_id')}`\n"
        f"➥ ᴀᴅᴅᴇᴅ ʙʏ » `{d.get('added_by')}`\n"
        f"➥ ꜱᴛᴀᴛᴜꜱ » {d.get('status')}"
        f"{' (ʀᴜɴɴɪɴɢ)' if c and c.is_running() else ''}{extra}"
    )


@app.on_message(filters.private & filters.command(["delallclone"]) & _owner_filter())
async def _del_all(_, m: types.Message):
    if len(m.command) > 1 and m.command[1] == "confirm":
        n = await get_manager().delete_all(m.from_user.id)
        return await m.reply_text(f"**✅ {n} ᴄʟᴏɴᴇ(ꜱ) ᴅᴇʟᴇᴛᴇᴅ ✔**")
    await m.reply_text(
        "**⚠️ ᴛʜɪꜱ ᴅᴇʟᴇᴛᴇꜱ ᴇᴠᴇʀʏ ᴄʟᴏɴᴇ ᴀɴᴅ ᴛʜᴇɪʀ ᴄᴜꜱᴛᴏᴍɪᴢᴀᴛɪᴏɴ !**\n\n"
        "➥ ᴄᴏɴꜰɪʀᴍ » `/delallclone confirm`"
    )

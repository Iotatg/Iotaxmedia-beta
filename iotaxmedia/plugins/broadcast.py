# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import asyncio
import os

from pyrogram import errors, filters, types

from iotaxmedia import app, db, lang, userbot

broadcasting = asyncio.Lock()


@app.on_message(filters.command(["broadcast"]) & app.sudoers)
@lang.language()
async def _broadcast(_, message: types.Message):
    if not message.reply_to_message:
        return await message.reply_text(message.lang["gcast_usage"])

    if broadcasting.locked():
        return await message.reply_text(message.lang["gcast_active"])

    msg = message.reply_to_message
    copy = "-copy" in message.command
    silent = "-silent" in message.command
    pin = "-pin" in message.command or "-pinloud" in message.command
    pin_loud = "-pinloud" in message.command
    assistant_mode = "-assistant" in message.command
    no_bot = "-nobot" in message.command
    count, ucount, acount = 0, 0, 0
    groups, users = set(), set()
    sent = await message.reply_text(message.lang["gcast_start"])

    if not no_bot:
        if "-nochat" not in message.command:
            groups = set(await db.get_chats())
        if "-user" in message.command:
            users = set(await db.get_users())

    chats = list(groups | users)
    failed = None

    async with broadcasting:
        for chat in chats:
            try:
                delivered = (
                    await msg.copy(
                        chat,
                        reply_markup=msg.reply_markup,
                        disable_notification=silent,
                    )
                    if copy
                    else await msg.forward(chat, disable_notification=silent)
                )
                if pin and chat in groups and delivered:
                    try:
                        await delivered.pin(disable_notification=not pin_loud)
                    except Exception:
                        pass
                if chat in groups:
                    count += 1
                else:
                    ucount += 1
                await asyncio.sleep(0.2)
            except errors.FloodWait as fw:
                await asyncio.sleep(fw.value + 10)
            except Exception as ex:
                if not failed:
                    failed = open("errors.txt", "w")
                failed.write(f"{chat} - {ex}\n")
                continue

        if assistant_mode:
            acount = await _broadcast_assistants(
                message, msg, copy, silent, pin, pin_loud, failed
            )

    text = message.lang["gcast_end"].format(count, ucount)
    if assistant_mode:
        text += f"\nAssistant groups: {acount}"
    if failed:
        failed.close()
        await message.reply_document(
            document="errors.txt",
            caption=text,
        )
        try:
            os.remove("errors.txt")
        except Exception:
            pass

    await sent.edit_text(text)


async def _broadcast_assistants(message, msg, copy, silent, pin, pin_loud, failed):
    sent = 0
    for ub in userbot.clients:
        if ub is None:
            continue
        try:
            async for dialog in ub.get_dialogs():
                chat_id = dialog.chat.id
                if chat_id > 0:
                    continue
                try:
                    if copy:
                        delivered = await ub.send_message(
                            chat_id,
                            msg.text or msg.caption or "",
                            disable_notification=silent,
                        )
                    else:
                        delivered = await ub.forward_messages(
                            chat_id,
                            message.chat.id,
                            msg.id,
                            disable_notification=silent,
                        )
                    sent += 1
                    if pin and delivered:
                        try:
                            await delivered.pin(disable_notification=not pin_loud)
                        except Exception:
                            pass
                    await asyncio.sleep(3)
                except errors.FloodWait as fw:
                    await asyncio.sleep(fw.value + 10)
                except Exception as ex:
                    if failed is not None:
                        failed.write(f"assistant {chat_id} - {ex}\n")
                    continue
        except Exception as ex:
            if failed is not None:
                failed.write(f"assistant dialogs - {ex}\n")
            continue
    return sent

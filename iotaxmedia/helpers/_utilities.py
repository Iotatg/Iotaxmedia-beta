# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import re
import time

from pyrogram import enums, types

from iotaxmedia import app, logger
from iotaxmedia._fonts import stylish


class Utilities:
    def __init__(self):
        pass

    def format_eta(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}:{seconds % 60:02d} min"
        else:
            h = seconds // 3600
            m = (seconds % 3600) // 60
            s = seconds % 60
            return f"{h}:{m:02d}:{s:02d} h"

    def format_size(self, bytes: int) -> str:
        if bytes >= 1024**3:
            return f"{bytes / 1024**3:.2f} GB"
        elif bytes >= 1024**2:
            return f"{bytes / 1024**2:.2f} MB"
        else:
            return f"{bytes / 1024:.2f} KB"

    def to_seconds(self, time: str) -> int:
        parts = [int(p) for p in time.strip().split(":")]
        return sum(value * 60**i for i, value in enumerate(reversed(parts)))

    def get_url(self, message_1: types.Message) -> str | None:
        link = None
        messages = [message_1]

        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)

        for message in messages:
            entities = message.entities or message.caption_entities or []

            for entity in entities:
                if entity.type == enums.MessageEntityType.TEXT_LINK:
                    link = entity.url
                    break
                elif entity.type == enums.MessageEntityType.URL:
                    text = message.text or message.caption
                    if not text:
                        continue
                    link = text[entity.offset : entity.offset + entity.length]
                    break

        if link:
            return link.split("&si")[0].split("?si")[0]
        return None

    async def extract_user(self, msg: types.Message) -> types.User | None:
        if msg.reply_to_message:
            return msg.reply_to_message.from_user

        if msg.entities:
            for e in msg.entities:
                if e.type == enums.MessageEntityType.TEXT_MENTION:
                    return e.user

        if msg.text:
            try:
                if m := re.search(r"@(\w{5,32})", msg.text):
                    return await app.get_users(m.group(0))
                if m := re.search(r"\b\d{6,15}\b", msg.text):
                    return await app.get_users(int(m.group(0)))
            except Exception:
                pass

        return None

    async def play_log(
        self,
        m: types.Message,
        link: str,
        title: str,
        duration: str,
        provider: str = "youtube",
        key: str = "",
        platform: str = "",
    ) -> None:
        if not app.owner:
            return
        chat = m.chat
        user = m.from_user
        chat_uname = f"@{chat.username}" if chat.username else "None"
        user_uname = f"@{user.username}" if user.username else "None"
        _text = (
            "CloneR Play Log ⚡\n\n"
            f"Chat id : <code>{chat.id}</code>\n"
            f"Chat name : {chat.title or chat.first_name or 'Private'}\n"
            f"Chat username : {chat_uname}\n\n"
            f"User id : <code>{user.id}</code>\n"
            f"Name : {user.first_name}\n"
            f"Username : {user_uname}\n\n"
            f"Streamtype : {provider}\n"
            f"Query : {title}"
        )
        _markup = [
            [
                types.InlineKeyboardButton(
                    text=stylish("User"),
                    style=enums.ButtonStyle.PRIMARY,
                    url=f"tg://user?id={user.id}",
                )
            ]
        ]
        if link:
            _markup[0].append(
                types.InlineKeyboardButton(
                    text=stylish("Where"),
                    style=enums.ButtonStyle.PRIMARY,
                    url=link,
                )
            )
        try:
            await app.send_message(
                chat_id=app.owner,
                text=stylish(_text),
                reply_markup=types.InlineKeyboardMarkup(_markup),
            )
        except Exception as exc:
            logger.error(f"[play_log] owner DM failed: {exc}")

    async def send_log(self, m: types.Message, chat: bool = False) -> None:
        if not app.owner:
            return
        _chat = m.chat
        _user = m.from_user
        chat_name = _chat.title or (_chat.first_name or "Private")
        chat_uname = f"@{_chat.username}" if _chat.username else "None"
        user_name = _user.first_name if _user else "Anonymous"
        user_uname = f"@{_user.username}" if _user and _user.username else "None"
        _text = (
            "CloneR Start Log ⚡\n\n"
            f"Chat id : <code>{_chat.id}</code>\n"
            f"Chat name : {chat_name}\n"
            f"Chat username : {chat_uname}\n\n"
            f"User id : <code>{_user.id if _user else 0}</code>\n"
            f"Name : {user_name}\n"
            f"Username : {user_uname}\n\n"
            f"Time : {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}"
        )
        _rows = []
        if _user:
            _rows.append(
                [
                    types.InlineKeyboardButton(
                        text=stylish("User"),
                        style=enums.ButtonStyle.PRIMARY,
                        url=f"tg://user?id={_user.id}",
                    )
                ]
            )
        try:
            await app.send_message(
                chat_id=app.owner,
                text=stylish(_text),
                reply_markup=types.InlineKeyboardMarkup(_rows) if _rows else None,
            )
        except Exception as exc:
            logger.error(f"[play_log] owner start-DM failed: {exc}")

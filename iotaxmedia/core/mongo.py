# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
from random import randint
from time import time

from pymongo import AsyncMongoClient

from iotaxmedia import config, logger, userbot


class MongoDB:
    def __init__(self):
        """
        Initialize the MongoDB connection.
        """
        self.mongo = AsyncMongoClient(config.MONGO_URL, serverSelectionTimeoutMS=12500)
        self.db = self.mongo.iotaxmedia
        self.connected = False

        self.admin_list = {}
        self.active_calls = {}
        self.admin_play = []
        self.blacklisted = []
        self.cmd_delete = []
        self.thumb_mode = []
        self.vclogger = {}
        self.loop = {}
        self.autoplay = []
        self.notified = []
        self.cache = self.db.cache
        self.logger = False

        self.assistant = {}
        self.assistantdb = self.db.assistant

        self.auth = {}
        self.authdb = self.db.auth

        self.chats = []
        self.chatsdb = self.db.chats



        self.play_counts = {}
        self.last_played = {}
        self.playstats = self.db.playstats

        self.lang = {}
        self.langdb = self.db.lang

        self.users = []
        self.usersdb = self.db.users
        self.user_names = {}
        self.user_namesdb = self.db.user_names


        self.anon_users: list[int] = []
        self._anon_neg: dict[int, float] = {}
        self.anondb = self.db.anon





        self.sticker_packs = self.db.sticker_packs

    async def connect(self) -> None:
        """Check if we can connect to the database.

        Raises:
            SystemExit: If the connection to the database fails.
        """
        try:
            start = time()
            await self.mongo.admin.command("ping")
            self.connected = True
            logger.info(f"Database connection successful. ({time() - start:.2f}s)")
            await self.load_cache()
        except Exception as e:
            self.connected = False
            logger.warning(f"Database connection failed: {type(e).__name__} - using in-memory storage only!")

    async def close(self) -> None:
        """Close the connection to the database."""
        await self.mongo.close()
        logger.info("Database connection closed.")


    async def get_call(self, chat_id: int) -> bool:
        return chat_id in self.active_calls

    async def add_call(self, chat_id: int) -> None:
        self.active_calls[chat_id] = 1

    async def remove_call(self, chat_id: int) -> None:
        self.active_calls.pop(chat_id, None)

    async def playing(self, chat_id: int, paused: bool = None) -> bool | None:
        if paused is not None:
            self.active_calls[chat_id] = int(not paused)
        return bool(self.active_calls.get(chat_id, 0))

    async def get_admins(self, chat_id: int, reload: bool = False) -> list[int]:
        from iotaxmedia.helpers._admins import reload_admins

        if chat_id not in self.admin_list or reload:
            self.admin_list[chat_id] = await reload_admins(chat_id)
        return self.admin_list[chat_id]

    async def get_loop(self, chat_id: int) -> int:
        return self.loop.get(chat_id, 0)

    async def set_loop(self, chat_id: int, count: int) -> None:
        self.loop[chat_id] = count


    async def _get_auth(self, chat_id: int) -> set[int]:
        if chat_id not in self.auth:
            doc = await self.authdb.find_one({"_id": chat_id}) or {}
            self.auth[chat_id] = set(doc.get("user_ids", []))
        return self.auth[chat_id]

    async def is_auth(self, chat_id: int, user_id: int) -> bool:
        return user_id in await self._get_auth(chat_id)

    async def add_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id not in users:
            users.add(user_id)
            await self.authdb.update_one(
                {"_id": chat_id}, {"$addToSet": {"user_ids": user_id}}, upsert=True
            )

    async def rm_auth(self, chat_id: int, user_id: int) -> None:
        users = await self._get_auth(chat_id)
        if user_id in users:
            users.discard(user_id)
            await self.authdb.update_one(
                {"_id": chat_id}, {"$pull": {"user_ids": user_id}}
            )


    async def set_assistant(self, chat_id: int) -> int:
        num = randint(1, len(userbot.clients))
        await self.assistantdb.update_one(
            {"_id": chat_id},
            {"$set": {"num": num}},
            upsert=True,
        )
        self.assistant[chat_id] = num
        return num

    async def get_assistant(self, chat_id: int):
        from iotaxmedia import iotaxmedia

        if chat_id not in self.assistant:
            doc = await self.assistantdb.find_one({"_id": chat_id})
            num = doc["num"] if doc else None

            if not num or num > len(iotaxmedia.clients):
                num = await self.set_assistant(chat_id)
            self.assistant[chat_id] = num

        return iotaxmedia.clients[self.assistant[chat_id] - 1]

    async def get_client(self, chat_id: int):
        if chat_id not in self.assistant:
            await self.get_assistant(chat_id)

        num = self.assistant[chat_id]
        if num > len(userbot.clients):
            num = await self.set_assistant(chat_id)
            self.assistant[chat_id] = num

        return {1: userbot.one, 2: userbot.two, 3: userbot.three}.get(num)


    async def add_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            self.blacklisted.append(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"},
                {"$addToSet": {"chat_ids": chat_id}},
                upsert=True,
            )
        await self.cache.update_one(
            {"_id": "bl_users"},
            {"$addToSet": {"user_ids": chat_id}},
            upsert=True,
        )

    async def del_blacklist(self, chat_id: int) -> None:
        if str(chat_id).startswith("-"):
            self.blacklisted.remove(chat_id)
            return await self.cache.update_one(
                {"_id": "bl_chats"},
                {"$pull": {"chat_ids": chat_id}},
            )
        await self.cache.update_one(
            {"_id": "bl_users"},
            {"$pull": {"user_ids": chat_id}},
        )

    async def get_blacklisted(self, chat: bool = False) -> list[int]:
        if chat:
            if not self.blacklisted:
                doc = await self.cache.find_one({"_id": "bl_chats"})
                self.blacklisted.extend(doc.get("chat_ids", []) if doc else [])
            return self.blacklisted
        doc = await self.cache.find_one({"_id": "bl_users"})
        return doc.get("user_ids", []) if doc else []


    async def is_chat(self, chat_id: int) -> bool:
        return chat_id in self.chats

    async def add_chat(self, chat_id: int) -> None:
        if not await self.is_chat(chat_id):
            self.chats.append(chat_id)
            await self.chatsdb.insert_one({"_id": chat_id})

    async def rm_chat(self, chat_id: int) -> None:
        if await self.is_chat(chat_id):
            self.chats.remove(chat_id)
            await self.chatsdb.delete_one({"_id": chat_id})

    async def get_chats(self) -> list:
        if not self.chats:
            self.chats.extend([chat["_id"] async for chat in self.chatsdb.find()])
        return self.chats


    async def get_cmd_delete(self, chat_id: int) -> bool:
        if chat_id not in self.cmd_delete:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("cmd_delete"):
                self.cmd_delete.append(chat_id)
        return chat_id in self.cmd_delete

    async def set_cmd_delete(self, chat_id: int, delete: bool = False) -> None:
        if delete:
            self.cmd_delete.append(chat_id)
        else:
            self.cmd_delete.remove(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"cmd_delete": delete}},
            upsert=True,
        )


    async def set_lang(self, chat_id: int, lang_code: str):
        await self.langdb.update_one(
            {"_id": chat_id},
            {"$set": {"lang": lang_code}},
            upsert=True,
        )
        self.lang[chat_id] = lang_code

    async def get_lang(self, chat_id: int) -> str:
        if chat_id not in self.lang:
            doc = await self.langdb.find_one({"_id": chat_id})
            self.lang[chat_id] = doc["lang"] if doc else config.LANG_CODE
        return self.lang[chat_id]


    async def is_logger(self) -> bool:
        return self.logger

    async def get_logger(self) -> bool:
        doc = await self.cache.find_one({"_id": "logger"})
        if doc:
            self.logger = doc["status"]
        return self.logger

    async def set_logger(self, status: bool) -> None:
        self.logger = status
        await self.cache.update_one(
            {"_id": "logger"},
            {"$set": {"status": status}},
            upsert=True,
        )



    async def note_play(self, chat_id: int) -> None:
        """Record one track start for a chat (count + recency)."""
        cid = int(chat_id)
        now = int(time())
        self.play_counts[cid] = self.play_counts.get(cid, 0) + 1
        self.last_played[cid] = now
        try:
            await self.playstats.update_one(
                {"_id": cid},
                {"$inc": {"plays": 1}, "$set": {"last_played": now}},
                upsert=True,
            )
        except Exception:
            pass

    async def get_play_count(self, chat_id: int) -> int:
        cid = int(chat_id)
        if cid not in self.play_counts:
            doc = await self.playstats.find_one({"_id": cid})
            self.play_counts[cid] = int(doc.get("plays", 0)) if doc else 0
        return self.play_counts[cid]

    async def get_last_played(self, chat_id: int) -> int:
        """Epoch of this chat's last track start (0 if never/unknown)."""
        cid = int(chat_id)
        if cid not in self.last_played:
            doc = await self.playstats.find_one({"_id": cid})
            self.last_played[cid] = int(doc.get("last_played", 0)) if doc else 0
        return self.last_played[cid]

    async def get_top_chats(self, limit: int = 10) -> list:
        """Top chats sorted by lifetime play count: [(chat_id, plays), ...]."""
        out = []
        try:
            cursor = (
                self.playstats.find({}, {"plays": 1})
                .sort("plays", -1)
                .limit(limit)
            )
            async for doc in cursor:
                plays = int(doc.get("plays", 0))
                if plays > 0:
                    out.append((int(doc["_id"]), plays))
        except Exception:
            pass
        return out

    async def get_thumb_mode(self, chat_id: int) -> bool:
        if chat_id not in self.thumb_mode:
            doc = await self.chatsdb.find_one({"_id": chat_id})

            if doc is None or doc.get("thumb_mode") is None:

                self.thumb_mode.append(chat_id)
                await self.chatsdb.update_one(
                    {"_id": chat_id},
                    {"$set": {"thumb_mode": True}},
                    upsert=True,
                )
            elif doc.get("thumb_mode"):
                self.thumb_mode.append(chat_id)
        return chat_id in self.thumb_mode

    async def set_thumb_mode(self, chat_id: int, status: bool = True) -> None:
        if status:
            if chat_id not in self.thumb_mode:
                self.thumb_mode.append(chat_id)
        else:
            if chat_id in self.thumb_mode:
                self.thumb_mode.remove(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"thumb_mode": status}},
            upsert=True,
        )

    async def get_autoplay(self, chat_id: int) -> bool:
        if chat_id not in self.autoplay:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("autoplay"):
                self.autoplay.append(chat_id)
        return chat_id in self.autoplay

    async def set_autoplay(self, chat_id: int, status: bool = False) -> None:
        if status:
            if chat_id not in self.autoplay:
                self.autoplay.append(chat_id)
        else:
            if chat_id in self.autoplay:
                self.autoplay.remove(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"autoplay": status}},
            upsert=True,
        )


    async def get_vclogger(self, chat_id: int) -> bool:
        if chat_id not in self.vclogger:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            self.vclogger[chat_id] = bool(doc and doc.get("vclogger"))
        return self.vclogger[chat_id]

    async def set_vclogger(self, chat_id: int, status: bool = False) -> None:
        self.vclogger[chat_id] = status
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"vclogger": status}},
            upsert=True,
        )


    async def get_welcome(self, chat_id: int) -> dict:
        """Return the welcome config for a chat.

        Shape: {enabled: bool, text: str|None, media: str|None,
        buttons: str|None}. ``buttons`` is the raw button spec string
        (``text - url | text - url`` rows separated by newlines).

        Sep 2026: default-enabled. New chats get a default Aisha-style
        greeting out of the box; admins can override with /setwelcome
        or disable with /welcometoggle off / /resetwelcome.
        """
        from iotaxmedia.helpers._welcome import DEFAULT_WELCOME

        doc = await self.chatsdb.find_one({"_id": chat_id}) or {}
        w = doc.get("welcome") or {}
        return {
            "enabled": bool(w.get("enabled", True)),
            "text": w.get("text") or DEFAULT_WELCOME,
            "media": w.get("media"),
            "buttons": w.get("buttons"),
        }

    async def set_welcome(self, chat_id: int, **fields) -> None:
        """Patch one or more welcome fields (enabled/text/media/buttons)."""
        update = {f"welcome.{k}": v for k, v in fields.items()}
        await self.chatsdb.update_one(
            {"_id": chat_id}, {"$set": update}, upsert=True
        )


    async def get_play_mode(self, chat_id: int) -> bool:
        if chat_id not in self.admin_play:
            doc = await self.chatsdb.find_one({"_id": chat_id})
            if doc and doc.get("admin_play"):
                self.admin_play.append(chat_id)
        return chat_id in self.admin_play

    async def set_play_mode(self, chat_id: int, remove: bool = False) -> None:
        if remove and chat_id in self.admin_play:
            self.admin_play.remove(chat_id)
        else:
            self.admin_play.append(chat_id)
        await self.chatsdb.update_one(
            {"_id": chat_id},
            {"$set": {"admin_play": not remove}},
            upsert=True,
        )


    async def add_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$addToSet": {"user_ids": user_id}}, upsert=True
        )

    async def del_sudo(self, user_id: int) -> None:
        await self.cache.update_one(
            {"_id": "sudoers"}, {"$pull": {"user_ids": user_id}}
        )

    async def get_sudoers(self) -> list[int]:
        doc = await self.cache.find_one({"_id": "sudoers"})
        return doc.get("user_ids", []) if doc else []


    async def is_user(self, user_id: int) -> bool:
        return user_id in self.users

    async def add_user(self, user_id: int) -> None:
        if not await self.is_user(user_id):
            self.users.append(user_id)
            await self.usersdb.insert_one({"_id": user_id})

    async def rm_user(self, user_id: int) -> None:
        if await self.is_user(user_id):
            self.users.remove(user_id)
            await self.usersdb.delete_one({"_id": user_id})

    async def get_users(self) -> list:
        if not self.users:
            self.users.extend([user["_id"] async for user in self.usersdb.find()])
        return self.users

    async def get_user_name(self, user_id: int) -> str:
        if user_id not in self.user_names:
            doc = await self.user_namesdb.find_one({"_id": user_id})
            self.user_names[user_id] = doc.get("name") if doc else None
        return self.user_names[user_id]

    async def set_user_name(self, user_id: int, name: str):
        self.user_names[user_id] = name
        await self.user_namesdb.update_one(
            {"_id": user_id},
            {"$set": {"name": name}},
            upsert=True
        )


    async def is_anon(self, user_id: int) -> bool:
        """Return True if the given user has Anonymous mode enabled."""
        if not user_id:
            return False
        if user_id in self.anon_users:
            return True
        neg = self._anon_neg.get(user_id)
        if neg and neg > time():
            return False

        doc = await self.anondb.find_one({"_id": user_id})
        if doc and doc.get("on"):
            self.anon_users.append(user_id)
            self._anon_neg.pop(user_id, None)
            return True
        if len(self._anon_neg) > 20000:
            now = time()
            self._anon_neg = {k: v for k, v in self._anon_neg.items() if v > now}
        self._anon_neg[user_id] = time() + 30
        return False

    async def set_anon(self, user_id: int, on: bool) -> None:
        """Enable or disable Anonymous mode for a user."""
        await self.anondb.update_one(
            {"_id": user_id},
            {"$set": {"on": bool(on)}},
            upsert=True,
        )
        self._anon_neg.pop(user_id, None)
        if on and user_id not in self.anon_users:
            self.anon_users.append(user_id)
        elif not on and user_id in self.anon_users:
            self.anon_users.remove(user_id)

    async def migrate_coll(self) -> None:
        logger.info("Migrating users and chats from old collections...")

        users, musers, mchats = [], [], []
        seen_chats, seen_users = set(), set()
        users.extend([user async for user in self.usersdb.find()])
        users.extend([user async for user in self.db.tgusersdb.find()])

        for user in users:
            _id = user.get("_id")
            if isinstance(_id, int):
                user_id = _id
            else:
                user_id = int(user.get("user_id"))

            if user_id in seen_users:
                continue
            seen_users.add(user_id)
            musers.append({"_id": user_id})

        await self.usersdb.drop()
        await self.db.tgusersdb.drop()
        if musers:
            await self.usersdb.insert_many(musers)

        async for chat in self.chatsdb.find():
            _id = chat.get("_id")
            if isinstance(_id, int):
                chat_id = _id
            else:
                chat_id = int(chat.get("chat_id"))

            if chat_id in seen_chats:
                continue
            seen_chats.add(chat_id)
            mchats.append({"_id": chat_id})

        await self.chatsdb.drop()
        if mchats:
            await self.chatsdb.insert_many(mchats)

        await self.cache.insert_one({"_id": "migrated"})
        logger.info("Migration completed successfully.")

    async def load_cache(self) -> None:
        doc = await self.cache.find_one({"_id": "migrated"})
        if not doc:
            await self.migrate_coll()

        await self.get_chats()
        await self.get_users()
        await self.get_blacklisted(True)
        await self.get_logger()


        try:
            async for d in self.anondb.find({"on": True}, {"_id": 1}):
                uid = d.get("_id")
                if isinstance(uid, int) and uid not in self.anon_users:
                    self.anon_users.append(uid)
        except Exception:
            pass

        logger.info("Database cache loaded.")

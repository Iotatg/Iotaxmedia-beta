# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Mongo persistence for the clone subsystem.

Uses its own AsyncMongoClient on the same MONGO_URL but a dedicated database
(``iotaxmedia_beta_clones``) so clone bookkeeping never mixes with the main
bot's caches. All methods are safe to call when the DB is briefly unreachable
only in the sense that they raise; callers decide fallback policy.
"""

from typing import Any, Optional

from pymongo import AsyncMongoClient


class CloneStore:
    def __init__(self, mongo_url: str):
        self.mongo = AsyncMongoClient(mongo_url, serverSelectionTimeoutMS=12500)
        self.db = self.mongo.iotaxmedia_beta_clones
        self.registry = self.db.registry
        self.settings = self.db.settings


    async def add_clone(self, token: str, owner_id: int, added_by: int) -> dict:
        from time import time

        doc = {
            "_id": token,
            "owner_id": int(owner_id),
            "added_by": int(added_by),
            "added_at": time(),
            "status": "active",
        }
        await self.registry.update_one(
            {"_id": token}, {"$set": doc}, upsert=True
        )
        return doc

    async def get_clone(self, token: str) -> Optional[dict]:
        return await self.registry.find_one({"_id": token})

    async def all_clones(self, status: Optional[str] = None) -> list:
        query = {"status": status} if status else {}
        return [doc async for doc in self.registry.find(query)]

    async def set_status(self, token: str, status: str) -> None:
        await self.registry.update_one(
            {"_id": token}, {"$set": {"status": status}}
        )

    async def delete_clone(self, token: str) -> None:

        await self.set_status(token, "deleted")
        await self.settings.delete_many({"clone_id": token})

    async def clones_for_owner(self, owner_id: int) -> list:
        query = {"owner_id": int(owner_id), "status": {"$ne": "deleted"}}
        return [doc async for doc in self.registry.find(query)]


    async def get_setting(
        self, clone_id: str, key: str, default: Any = None
    ) -> Any:
        doc = await self.settings.find_one({"_id": f"{clone_id}:{key}"})
        if not doc:
            return default
        value = doc.get("value", default)

        return doc.get(key, value)

    async def set_setting(self, clone_id: str, key: str, value: Any) -> Any:
        await self.settings.update_one(
            {"_id": f"{clone_id}:{key}"},
            {"$set": {"clone_id": clone_id, "key": key, "value": value}},
            upsert=True,
        )
        return value

    async def del_setting(self, clone_id: str, key: str) -> bool:
        result = await self.settings.delete_one({"_id": f"{clone_id}:{key}"})
        return result.deleted_count > 0

    async def wipe_settings(self, clone_id: str) -> None:
        await self.settings.delete_many({"clone_id": clone_id})

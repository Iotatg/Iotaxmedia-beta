# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Mongo helpers for mood-based sticker packs (sticker-to-sticker replies).

Same shape as IotaXMedia/utils/sticker_db.py and iota/utils/mongo_db.py:
a sticker_packs collection keyed by mood slug, with file_ids stored as a
list (de-duped via $addToSet). The bot's sticker-to-sticker reply engine
reads from here; the assistant userbot reads from the same collection.

The helpers read through a lazy get_db() so tests can patch without
importing the real Mongo client. Matches the iota/utils/mongo_db.py pattern.
"""
from datetime import datetime, timezone

import time

_CACHE_TTL = 30.0
_cache_at = 0.0
_cache_data = None


def _invalidate() -> None:
    global _cache_data, _cache_at
    _cache_data = None
    _cache_at = 0.0


def get_db():
    """Return the iotaxmedia-beta database handle.

    Resolved lazily so tests can monkey-patch this function with a fake
    collection and exercise the helpers without a real Mongo connection.
    """
    from iotaxmedia import db
    return db.db if hasattr(db, "db") else db


def _now():
    return datetime.now(timezone.utc)


async def add_sticker_to_pack(mood: str, file_id: str, added_by: int = 0) -> None:
    db = get_db()
    await db.sticker_packs.update_one(
        {"_id": mood.lower()},
        {
            "$addToSet": {"file_ids": file_id},
            "$set": {"updated_at": _now(), "updated_by": added_by},
        },
        upsert=True,
    )
    _invalidate()


async def remove_sticker_from_pack(mood: str, file_id: str) -> bool:
    db = get_db()
    result = await db.sticker_packs.update_one(
        {"_id": mood.lower()}, {"$pull": {"file_ids": file_id}}
    )
    _invalidate()
    return result.modified_count > 0


async def get_stickers_for_mood(mood: str) -> list:
    db = get_db()
    doc = await db.sticker_packs.find_one({"_id": mood.lower()})
    return doc.get("file_ids", []) if doc else []


async def list_all_sticker_packs() -> dict:
    global _cache_at, _cache_data
    now = time.monotonic()
    if _cache_data is not None and now - _cache_at < _CACHE_TTL:
        return _cache_data
    db = get_db()
    docs = await db.sticker_packs.find({}).to_list(1000)
    _cache_data = {
        d["_id"]: len(d.get("file_ids", []))
        for d in docs
        if isinstance(d.get("_id"), str)
    }
    _cache_at = now
    return _cache_data


async def clear_sticker_pack(mood: str) -> int:
    db = get_db()
    doc = await db.sticker_packs.find_one({"_id": mood.lower()})
    count = len(doc.get("file_ids", [])) if doc else 0
    await db.sticker_packs.delete_one({"_id": mood.lower()})
    _invalidate()
    return count


async def clear_all_sticker_packs() -> int:
    db = get_db()
    result = await db.sticker_packs.delete_many({})
    _invalidate()
    return result.deleted_count

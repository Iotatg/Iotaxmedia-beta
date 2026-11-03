# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""CloneManager: registry-backed lifecycle for in-process clones.

Lessons baked in (from the IotaXMedia implementation audit):
- double-checked locking around start_clone (no concurrent double-boot),
- failed boots never poison the module-tree snapshot,
- stop() reaps the task BEFORE dropping the tree,
- /delclone during boot wins via post-ready zombie re-check,
- revival is sequential and bounded.
"""

import asyncio
import logging
import re
from typing import Dict, List, Optional

from iotaxmedia.clone.db import CloneStore
from iotaxmedia.clone.runtime_inproc import InProcessClone, install_hook

logger = logging.getLogger("iotaxmedia.clone")

_TOKEN_RE = re.compile(r"^\d+:[A-Za-z0-9_-]{30,}$")

_store: Optional[CloneStore] = None
_manager: Optional["CloneManager"] = None


def get_store() -> CloneStore:
    global _store
    if _store is None:
        from iotaxmedia import config

        _store = CloneStore(config.MONGO_URL)
    return _store


def get_manager() -> "CloneManager":
    global _manager
    if _manager is None:
        _manager = CloneManager()
    return _manager



get_clone_manager = get_manager


def validate_token(token: str) -> bool:
    return bool(_TOKEN_RE.match((token or "").strip()))


class CloneManager:
    def __init__(self):
        self._clones: Dict[str, InProcessClone] = {}
        self._lock = None
        self._supervisor_task: Optional[asyncio.Task] = None

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def get_clone(self, token: str) -> Optional[InProcessClone]:
        return self._clones.get(token.strip())

    def running_tokens(self) -> List[str]:
        return [t for t, c in self._clones.items() if c.is_running()]


    async def start_clone(self, token: str, owner_id: int) -> bool:
        token = token.strip()
        if not validate_token(token):
            raise ValueError("Invalid bot token format.")
        store = get_store()
        async with self.lock:
            existing = self._clones.get(token)
            if existing is not None and existing.is_running():
                return True



            prev = await store.get_clone(token)
            prev_status = prev.get("status") if prev else None
            if (
                prev
                and int(prev.get("owner_id") or 0) == int(owner_id)
                and prev_status != "deleted"
            ):
                await store.set_status(token, "active")
            else:
                await store.add_clone(token, owner_id, owner_id)
            clone = InProcessClone(token)
            self._clones[token] = clone
            ok = await clone.start()
        if not ok:
            self._clones.pop(token, None)

            if prev is None or prev_status == "deleted":
                await store.set_status(token, "deleted")
            elif prev_status:
                await store.set_status(token, prev_status)
            return False
        logger.info(f"[BETA_CLONE] {token[:12]}… started by {owner_id}")
        return True

    async def stop_clone(self, token: str) -> bool:
        token = token.strip()



        async with self.lock:
            clone = self._clones.pop(token, None)
            if clone is None:
                return False
            await get_store().set_status(token, "stopped")
            await clone.stop()
        logger.info(f"Clone {token[:12]}… stopped.")
        return True

    async def restart_clone(self, token: str) -> bool:
        token = token.strip()
        store = get_store()
        record = await store.get_clone(token)
        owner_id = int(record.get("owner_id") or 0) if record else 0
        await self.stop_clone(token)
        if owner_id:
            return await self.start_clone(token, owner_id)
        return False

    def schedule_bounce(self, token: str, delay: float = 60.0) -> None:
        """Graceful self-bounce, safe to schedule from INSIDE the clone.

        Unlike restart_clone (which must never run on the clone's own task),
        the bounce waits for the running task to finish before starting fresh.
        """
        asyncio.get_running_loop().create_task(self._bounce(token.strip(), delay))

    async def _bounce(self, token: str, delay: float) -> bool:
        await asyncio.sleep(delay)
        clone = self._clones.get(token)
        if clone is None:
            return False
        record = await get_store().get_clone(token)
        if not record or record.get("status") != "active":
            return False
        owner_id = int(record.get("owner_id") or 0)
        if clone.is_running():
            clone.shutdown_event.set()
            try:
                await asyncio.wait_for(asyncio.shield(clone.task), 90)
            except Exception:
                pass
            self._clones.pop(token, None)
        return await self.start_clone(token, owner_id)

    async def delete_clone(self, token: str) -> bool:
        token = token.strip()
        store = get_store()




        existed = await store.get_clone(token) is not None
        await store.set_status(token, "deleted")
        await store.wipe_settings(token)
        async with self.lock:
            clone = self._clones.pop(token, None)
            if clone is not None:
                await clone.stop()
        logger.info(f"Clone {token[:12]}… deleted.")
        return existed

    async def delete_all(self, deleter_id: int) -> int:
        count = 0
        for doc in await get_store().all_clones():
            if doc.get("status") == "deleted":
                continue
            await self.delete_clone(doc["_id"])
            count += 1
        logger.info(f"{count} clone(s) deleted by {deleter_id}.")
        return count


    async def revive_pending(self) -> int:
        """Start registry-active clones that are not running (boot recovery)."""
        revived = 0
        try:
            docs = await get_store().all_clones(status="active")
        except Exception as exc:
            logger.warning(f"Clone revival skipped (registry unreachable): {exc}")
            return 0
        for doc in docs:
            token = doc["_id"]
            clone = self._clones.get(token)
            if clone is not None and clone.is_running():
                continue
            try:
                if await self.start_clone(token, int(doc.get("owner_id") or 0)):
                    revived += 1
            except Exception as exc:
                logger.error(f"Clone {token[:12]}… revival failed: {exc}")
        return revived

    async def supervisor(self, interval: int = 300) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                await self.revive_pending()
            except Exception as exc:
                logger.error(f"Clone supervisor error: {exc}")

    def start_supervisor(self) -> None:
        if self._supervisor_task is None or self._supervisor_task.done():
            self._supervisor_task = asyncio.create_task(self.supervisor())

    async def shutdown_all(self) -> None:
        tokens = list(self._clones.keys())
        await asyncio.gather(
            *(self._clones[t].stop() for t in tokens), return_exceptions=True
        )
        for t in tokens:
            self._clones.pop(t, None)
        logger.info(f"All clones stopped ({len(tokens)}).")


install_hook()

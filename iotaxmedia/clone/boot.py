# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Clone boot sequence: mirrors beta's main() inside the clone's namespace.

Runs as the clone's asyncio task with ``_CLONE_CTX`` already raised, so every
``from iotaxmedia import …`` resolves through the hook to THIS clone's fresh
tree (tree is captured only after success).
"""

import logging

logger = logging.getLogger("iotaxmedia.clone")


_EXCLUDED_PLUGINS = {"clonemanager"}


async def run(clone) -> None:
    """Boot one clone to readiness, then park until shutdown is requested."""
    token = clone.token



    from iotaxmedia.clone.customization import (
        get_clone_channel,
        get_clone_logger,
        get_clone_name,
        get_clone_string,
        get_clone_support,
    )
    from iotaxmedia.clone.runtime import get_store

    store = get_store()
    record = await store.get_clone(token)
    if not record or record.get("status") != "active":
        logger.warning(f"Clone {token[:12]}… registry inactive — aborting boot.")
        return
    owner_id = int(record.get("owner_id") or 0)





    import os

    own_string = await get_clone_string(token)
    borrowing = not own_string
    custom_name = await get_clone_name(token)
    custom_logger = await get_clone_logger(token)
    custom_channel = await get_clone_channel(token)
    custom_support = await get_clone_support(token)

    _ENV_KEYS = (
        "SESSION1",
        "SESSION2",
        "SESSION3",
        "LOGGER_ID",
        "OWNER_ID",
        "BOT_NAME",
        "SUPPORT_CHANNEL",
        "SUPPORT_CHAT",
        "CLONE_OWNER_ID",
    )
    saved_env = {k: os.environ.get(k) for k in _ENV_KEYS}

    def _shape_env() -> None:


        os.environ["SESSION1"] = own_string or ""
        os.environ["SESSION2"] = ""
        os.environ["SESSION3"] = ""
        os.environ["OWNER_ID"] = str(owner_id)
        os.environ["CLONE_OWNER_ID"] = str(owner_id)

        os.environ["LOGGER_ID"] = str(custom_logger or 0)
        if custom_name:
            os.environ["BOT_NAME"] = custom_name
        if custom_channel:
            os.environ["SUPPORT_CHANNEL"] = custom_channel
        if custom_support:
            os.environ["SUPPORT_CHAT"] = custom_support

    def _restore_env() -> None:
        for key, value in saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    _shape_env()
    try:



        await _run_boot(clone, token, owner_id, borrowing, store, _restore_env)
    finally:
        _restore_env()


async def _run_boot(
    clone, token: str, owner_id: int, borrowing: bool, store, _restore_env
) -> None:

    pkg = __import__("iotaxmedia", globals(), locals(), ["app"], 0)
    app, db, userbot, calls = pkg.app, pkg.db, pkg.userbot, pkg.iotaxmedia
    clone.app = app

    await db.connect()

    if borrowing:
        from iotaxmedia.clone import borrow
        from iotaxmedia.clone.runtime_inproc import _snapshot_current_tree

        tree = _snapshot_current_tree()
        ok = borrow.apply_borrow_mode(tree, token, owner_id)
        if not ok:
            logger.error(
                f"Clone {token[:12]}… cannot borrow assistants; aborting."
            )
            return
    else:
        await userbot.boot()
        await calls.boot()

    await app.boot()
    _restore_env()


    import asyncio
    import importlib

    from iotaxmedia.plugins import all_modules

    for module in sorted(all_modules):
        if module in _EXCLUDED_PLUGINS:
            continue
        importlib.import_module(f"iotaxmedia.plugins.{module}")
    logger.info(f"Clone {token[:12]}… loaded {len(all_modules)} plugin modules.")

    from iotaxmedia.clone.handlers import register_clone_handlers

    register_clone_handlers(app, token, owner_id)


    record = await store.get_clone(token)
    if not record or record.get("status") != "active":
        logger.warning(f"Clone {token[:12]}… deleted during boot — tearing down.")
        return

    clone.plugins_ready.set()
    logger.info(f"[BETA_CLONE] {token.split(':')[0]} ready (borrow={borrowing})")

    try:
        await clone.shutdown_event.wait()
    finally:
        for task in list(pkg.tasks):
            task.cancel()
        try:
            await asyncio.wait_for(app.exit(), timeout=15)
        except Exception:
            pass
        if not borrowing:
            try:
                await userbot.exit()
            except Exception:
                pass

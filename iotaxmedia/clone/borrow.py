# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Borrow mode: clones without their own session strings reuse the MAIN bot's
assistants and playback state.

Rule learned from the IotaXMedia split-brain bug: mutable state containers are
rebound ONTO THE SAME OBJECTS (identity, never copies), and this happens
BEFORE plugin import so decorated filters and captured references see them.
"""

import builtins
import logging
import traceback

from pyrogram import filters

logger = logging.getLogger("iotaxmedia.clone")


_DB_CONTAINERS = (
    "admin_list",
    "active_calls",
    "admin_play",
    "blacklisted",
    "cmd_delete",
    "thumb_mode",
    "vclogger",
    "loop",
    "autoplay",
    "notified",
    "assistant",
    "auth",
    "chats",
    "lang",
)

CLONE_BORROW = False


def _seeded_filter(*user_ids: int):

    flt = filters.user(0)
    flt.clear()
    flt.update({int(u) for u in user_ids if u})
    return flt


def apply_borrow_mode(tree: dict, token: str, clone_owner_id: int) -> bool:
    """Rebind clone-tree singletons onto the main bot's live objects.

    ``tree`` maps scoped module names to the clone's fresh modules. Returns
    True when rebinding happened, False when the main assistants are not
    booted yet (caller should abort or fall back to own sessions).
    """
    global CLONE_BORROW

    pkg = tree.get("iotaxmedia")
    if pkg is None:
        logger.error("Borrow abort: clone tree has no iotaxmedia package.")
        return False
    try:
        main_pkg = sys_main_pkg()
    except Exception:
        logger.error(
            "Borrow abort: sys_main_pkg() failed:\n" + traceback.format_exc()
        )
        return False

    main_userbot = getattr(main_pkg, "userbot", None)
    if (
        main_userbot is None
        or not getattr(main_userbot, "clients", None)
        or main_userbot.clients[0] is None
    ):
        logger.warning(
            f"Borrow abort: main assistants not booted "
            f"(userbot={main_userbot!r}, "
            f"clients={getattr(main_userbot, 'clients', None)!r})."
        )
        return False

    clone_userbot = pkg.userbot
    clone_userbot.one = main_userbot.one
    clone_userbot.two = main_userbot.two
    clone_userbot.three = main_userbot.three
    clone_userbot.clients = main_userbot.clients

    clone_calls = pkg.iotaxmedia
    main_calls = main_pkg.iotaxmedia
    clone_calls.clients = main_calls.clients

    clone_queue = pkg.queue
    clone_queue.queues = main_pkg.queue.queues

    clone_db = pkg.db
    main_db = main_pkg.db
    for attr in _DB_CONTAINERS:
        setattr(clone_db, attr, getattr(main_db, attr))

    clone_app = pkg.app
    main_app = main_pkg.app


    sudo_ids = {int(u) for u in (main_app.sudoers or set()) if u}
    black_ids = {int(u) for u in (main_app.bl_users or set()) if u}
    clone_app.sudoers = _seeded_filter(clone_owner_id, *sudo_ids)
    clone_app.bl_users = _seeded_filter(*black_ids)

    CLONE_BORROW = True
    logger.info(
        f"Clone {token[:12]}… borrowed MAIN bot assistants "
        f"({len(main_userbot.clients)}) and shared playback state."
    )
    return True


def sys_main_pkg():
    """Return the MAIN bot's package module (never the calling clone's copy).

    Resolution order:
    1. builtins._BETA_MAIN_PKG — bridge handed over by InProcessClone.start()
       during the boot window (authoritative).
    2. builtins._IOTAX_PARENT_PKG — captured once by the parent copy of
       runtime_inproc at process startup; immune to window/bridge gaps.
    3. The saved window snapshot (legacy path).
    4. Plain import — LAST resort only, and rejected when it resolves to a
       clone-tree copy (checked via CLONE_MODE), since that would silently
       "borrow" the clone's own unbooted singletons.
    """
    mod = getattr(builtins, "_BETA_MAIN_PKG", None)
    if mod is not None:
        return mod
    mod = getattr(builtins, "_IOTAX_PARENT_PKG", None)
    if mod is not None:
        return mod
    from iotaxmedia.clone.runtime_inproc import _get_window

    window = _get_window()
    if window:
        mod = window.get("iotaxmedia")
        if mod is not None:
            return mod
    import os as _os

    if _os.environ.get("CLONE_MODE") == "1":
        raise RuntimeError(
            "sys_main_pkg: no parent package reference available "
            "(bridge+sentinel+window all absent) inside CLONE_MODE"
        )
    import iotaxmedia

    return iotaxmedia

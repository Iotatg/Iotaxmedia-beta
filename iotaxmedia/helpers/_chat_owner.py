# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import builtins











def _store() -> dict:
    d = getattr(builtins, "_BETA_CHAT_OWNER", None)
    if d is None:
        d = {}
        builtins._BETA_CHAT_OWNER = d
    return d


def set_chat_owner(chat_id: int, bot_id: int) -> None:
    try:
        _store()[int(chat_id)] = int(bot_id)
    except (TypeError, ValueError):
        pass


def get_chat_owner(chat_id: int):
    try:
        return _store().get(int(chat_id))
    except (TypeError, ValueError):
        return None


def resolve_app(chat_id: int):
    """Return the bot client that owns this chat's playback.

    Falls back to the main bot when the chat was never stamped by a clone or
    the owning clone is no longer running.
    """
    import logging

    main_pkg = getattr(builtins, "_BETA_MAIN_PKG", None)
    if main_pkg is None:
        import iotaxmedia as main_pkg
    main_app = main_pkg.app
    bot_id = get_chat_owner(chat_id)
    if not bot_id or bot_id == main_app.id:
        logging.getLogger(__name__).warning(
            f"[BETA-OWNER-RESOLVE] chat={chat_id} owner={bot_id} "
            f"-> main(app={main_app.id})"
        )
        return main_app
    try:
        import importlib

        runtime = importlib.import_module("iotaxmedia.clone.runtime")
        for clone in runtime.get_manager()._clones.values():
            capp = getattr(clone, "app", None)
            if capp is not None and getattr(capp, "id", None) == bot_id:
                logging.getLogger(__name__).warning(
                    f"[BETA-OWNER-RESOLVE] chat={chat_id} owner={bot_id} "
                    f"-> clone(app={capp.id}, session={getattr(capp, 'name', '?')})"
                )
                return capp
    except Exception as e:
        logging.getLogger(__name__).warning(
            f"[BETA-OWNER-RESOLVE] chat={chat_id} owner={bot_id} lookup-error={e!r}"
        )
    logging.getLogger(__name__).warning(
        f"[BETA-OWNER-RESOLVE] chat={chat_id} owner={bot_id} no-running-clone -> main"
    )
    return main_app

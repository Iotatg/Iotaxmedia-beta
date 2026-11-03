# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import asyncio
import importlib
import signal
from contextlib import suppress

from iotaxmedia import app, iotaxmedia, config, db, logger, stop, thumb, userbot, yt
from iotaxmedia.plugins import all_modules


async def idle():
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGABRT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()


async def _boot_with_flood_guard(coro_factory, label: str):
    """Login calls can hit Telegram FloodWait (esp. after rapid redeploy
    loops). Wait it out INSIDE the process instead of crash-restarting into
    another immediate auth attempt.

    Also catches *fatal* auth errors (e.g. ``AuthKeyDuplicated`` — the same
    session string used in more than one place simultaneously) and exits
    cleanly with a clear, actionable message instead of letting the
    exception bubble up and the container crash-loop.
    """
    from pyrogram.errors import (
        AuthKeyDuplicated,
        AuthKeyInvalid,
        AuthKeyUnregistered,
        FloodWait,
        SessionRevoked,
        UserDeactivated,
    )

    for attempt in range(6):
        try:
            await coro_factory()
            return
        except FloodWait as e:
            wait = int(e.value) + 5
            logger.warning(
                f"{label}: Telegram FloodWait {wait}s "
                f"(attempt {attempt + 1}/6) — waiting patiently."
            )
            await asyncio.sleep(wait)
        except (
            AuthKeyDuplicated,
            AuthKeyInvalid,
            AuthKeyUnregistered,
            SessionRevoked,
            UserDeactivated,
        ) as e:




            kind = type(e).__name__
            logger.error(
                f"{label}: fatal auth error ({kind}: {e!s}). "
                "The session/bot token is invalid or is being used in "
                "more than one place. Stop any other instance using the "
                "same SESSION* / BOT_TOKEN, then redeploy. Exiting now "
                "to avoid a crash loop."
            )
            raise SystemExit(1) from e
    raise RuntimeError(f"{label}: repeated Telegram FloodWait, giving up.")


async def main():
    await db.connect()
    await thumb.start()
    await _boot_with_flood_guard(app.boot, "Bot login")
    await _boot_with_flood_guard(userbot.boot, "Assistant login")
    await iotaxmedia.boot()

    for module in all_modules:
        importlib.import_module(f"iotaxmedia.plugins.{module}")
    logger.info(f"Loaded {len(all_modules)} modules.")



    try:
        from iotaxmedia.plugins.assistant_chat import register as _register_assistant_chat

        _register_assistant_chat()
    except Exception as e:
        logger.warning(f"assistant_chat register failed: {e}")



    try:
        from iotaxmedia.plugins.sticker_reply_assis import register as _register_sticker_assis

        _register_sticker_assis()
    except Exception as e:
        logger.warning(f"sticker_reply_assis register failed: {e}")

    if config.COOKIES_URL:
        await yt.save_cookies(config.COOKIES_URL)

    sudoers = await db.get_sudoers()
    app.sudoers.update(sudoers)
    app.bl_users.update(await db.get_blacklisted())
    logger.info(f"Loaded {len(app.sudoers)} sudo users.")


    from iotaxmedia.clone.runtime import get_manager

    manager = get_manager()
    revived = await manager.revive_pending()
    manager.start_supervisor()
    if revived:
        logger.info(f"Clone manager: {revived} clone(s) revived.")

    await idle()
    asyncio.create_task(stop())


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        pass
    except SystemExit as e:


        raise SystemExit(e.code) from None

# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import asyncio
import logging
import time
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


__version__ = "3.0.3"

from config import Config

config = Config()
config.check()
tasks = []
boot = time.time()

from iotaxmedia.core.bot import Bot

app = Bot()

from iotaxmedia.core.dir import ensure_dirs

ensure_dirs()

from iotaxmedia.core.userbot import Userbot

userbot = Userbot()

from iotaxmedia.core.mongo import MongoDB

db = MongoDB()

from iotaxmedia.core.lang import Language

lang = Language()

from iotaxmedia.core.telegram import Telegram
from iotaxmedia.core.youtube import YouTube

tg = Telegram()
yt = YouTube()

from iotaxmedia.helpers import Queue, Thumbnail

queue = Queue()
thumb = Thumbnail()

from iotaxmedia.core.calls import TgCall

iotaxmedia = TgCall()


async def stop() -> None:
    logger.info("Stopping...")
    try:
        from iotaxmedia.clone.runtime import get_manager

        await get_manager().shutdown_all()
    except Exception as e:
        logger.warning(f"Clone shutdown skipped: {e}")
    await thumb.close()
    for task in tasks:
        task.cancel()
        try:
            await task
        except asyncio.exceptions.CancelledError:
            pass

    await app.exit()
    await userbot.exit()
    await db.close()

    logger.info("Stopped.\n")

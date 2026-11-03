# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
from os import getenv

from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.API_ID = int(getenv("API_ID", 0))
        self.API_HASH = getenv("API_HASH")

        self.BOT_TOKEN = getenv("BOT_TOKEN")
        self.MONGO_URL = getenv("MONGO_URL")

        self.LOGGER_ID = int(getenv("LOGGER_ID", 0))
        self.OWNER_ID = int(getenv("OWNER_ID", 0))
        self.OWNER_USERNAME = getenv("OWNER_USERNAME", "@im_ntg")
        self.OWNER_LINK = f"https://t.me/{self.OWNER_USERNAME.lstrip('@')}"

        self.DURATION_LIMIT = int(getenv("DURATION_LIMIT", 14400)) * 14400
        self.QUEUE_LIMIT = int(getenv("QUEUE_LIMIT", 20))
        self.PLAYLIST_LIMIT = int(getenv("PLAYLIST_LIMIT", 20))

        self.SESSION1 = getenv("SESSION", None)
        self.SESSION2 = getenv("SESSION2", None)
        self.SESSION3 = getenv("SESSION3", None)


        self.APINEX_API_KEY = getenv("APINEX_API_KEY", "")
        self.APINEX_MODEL = getenv("APINEX_MODEL", "free/glm-5.3-flash")
        self.APINEX_FALLBACK_MODEL = getenv("APINEX_FALLBACK_MODEL", "free/deepseek-v4-flash-0731")
        self.APINEX_API_URL = "https://api.apinex.bond/v1/chat/completions"


        self.OPENROUTER_API_KEY = getenv("OPENROUTER_API_KEY", "")
        self.OPENROUTER_MODEL = getenv(
            "OPENROUTER_MODEL", "dots-studio/dots-3-note-preview:free"
        )
        self.OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"




        self.CLONE_MODE = getenv("CLONE_MODE") == "1"
        self.CLONE_TOKEN = getenv("CLONE_TOKEN", None)

        self.SUPPORT_CHANNEL = getenv("SUPPORT_CHANNEL", "https://t.me/IotaUpdates")
        self.SUPPORT_CHAT = getenv("SUPPORT_CHAT", "https://t.me/samvadacha_chat")


        self.API_URL = getenv("SHRUTI_API_URL", "https://api.shrutibots.site")
        self.API_KEY = getenv("SHRUTI_API_KEY", "ShrutiBotsgBDkKisTQy4dawsleMKu")
        self.YUKI_API_URL = getenv("YUKI_API_URL", "https://music.yukiapi.site")
        self.YUKI_API_KEY = getenv("YUKI_API_KEY", "")

        self.AUTO_LEAVE: bool = getenv("AUTO_LEAVE", "False").lower() == "true"
        self.AUTO_END: bool = getenv("AUTO_END", "False").lower() == "true"

        self.THUMB_GEN: bool = getenv("THUMB_GEN", "True").lower() != "false"
        self.VIDEO_PLAY: bool = getenv("VIDEO_PLAY", "True").lower() == "true"

        self.LANG_CODE = getenv("LANG_CODE", "en")
        self.BOT_NAME = getenv("BOT_NAME", "𝐈ᴏᴛᴀ ✘ ʙєᴛᴀ")

        self.COOKIES_URL = [
            url
            for url in getenv("COOKIES_URL", "").split(" ")
            if url and "batbin.me" in url
        ]
        self.DEFAULT_THUMB = getenv(
            "DEFAULT_THUMB", "https://te.legra.ph/file/3e40a408286d4eda24191.jpg"
        )
        self.PING_IMG = getenv(
            "PING_IMG",
            "https://graph.org/file/a3cc654217d68297d8538-f0ae69bbb7a360f6ae.jpg",
        )
        self.START_VIDEO = getenv(
            "START_VIDEO",
            "https://graph.org/file/ad15e8b2f052e78256339-0c87eb7568d3e947e7.mp4",
        )

    def check(self):


        clone_mode = getenv("CLONE_MODE") == "1"
        required = [
            var
            for var in [
                "API_ID",
                "API_HASH",
                "BOT_TOKEN",
                "MONGO_URL",
                "OWNER_ID",
            ]
            if not getattr(self, var)
        ]
        if not clone_mode:
            required += [
                var
                for var in ["LOGGER_ID", "SESSION1"]
                if not getattr(self, var)
            ]
        if required:
            raise SystemExit(
                f"Missing required environment variables: {', '.join(required)}"
            )

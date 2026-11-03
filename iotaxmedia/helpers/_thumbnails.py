# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
from iotaxmedia import config
from iotaxmedia.helpers import Track


class Thumbnail:
    async def start(self):
        return True

    async def close(self):
        return True

    async def generate(self, song: Track) -> str:
        """
        Return the track's real platform thumbnail (YouTube / Spotify / etc.)
        directly. No branding or generated card is applied.
        """
        thumb = getattr(song, "thumbnail", None)
        if isinstance(thumb, str) and thumb.startswith("http"):
            return thumb.split("?")[0]
        return config.DEFAULT_THUMB

# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Async client for the nubcoders YT-DLP wrapper API.

Mirror of IotaXMedia/platforms/nubcoders.py so the iotaxmedia-beta tree can
use the same primary downloader / suggestion source. Token comes from
``config.NUB_API_KEY``; when empty the client is a no-op (bot falls back
to Shruti / Inflex / yt-dlp / lily).
"""

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from iotaxmedia import config

logger = logging.getLogger(__name__)


def _mask_key(key: Optional[str]) -> str:
    if not key:
        return "<unset>"
    if len(key) <= 10:
        return key[:2] + "***"
    return f"{key[:6]}…{key[-4:]}"


class NubApi:
    """Thin async wrapper around api.nubcoders.com.

    Falls back gracefully when the token is missing: every method returns
    ``None`` / ``[]`` instead of raising.
    """

    def __init__(
        self,
        api_url: str,
        api_key: str,
        *,
        timeout: int = 30,
    ):
        self.base = api_url.rstrip("/") or "https://api.nubcoders.com"
        self.api_key = api_key or ""
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _get(self, path: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            session = await self._get_session()
            url = f"{self.base}{path}"
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    logger.warning(
                        "[NUB] %s HTTP %d (key=%s)", path, resp.status, _mask_key(self.api_key)
                    )
                    return None
                return await resp.json(content_type=None)
        except Exception as e:
            logger.warning("[NUB] %s exception: %s", path, e)
            return None

    async def get_info(self, url_or_query: str) -> Optional[Dict[str, Any]]:
        """Return full info dict for a YouTube URL or search query.

        Result includes at least: ``stream_url``, ``title``, ``duration``,
        ``channel_name``, ``video_id``, ``thumbnail``, ``youtube_link`` and
        ``suggested[]`` (related tracks).
        """
        return await self._get(
            "/info", {"token": self.api_key, "q": url_or_query, "max_results": 1}
        )

    async def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Free text search — no token consumed."""
        if not query:
            return []
        try:
            session = await self._get_session()
            url = f"{self.base}/search"
            async with session.get(
                url, params={"q": query, "max_results": max_results}
            ) as resp:
                if resp.status != 200:
                    logger.warning("[NUB] /search HTTP %d", resp.status)
                    return []
                data = await resp.json(content_type=None)
            return list(data.get("results") or [])
        except Exception as e:
            logger.warning("[NUB] /search exception: %s", e)
            return []

    async def get_rate_limit(self) -> Optional[Dict[str, Any]]:
        """Quota snapshot — ``requests_used`` / ``daily_limit`` / ``remaining``."""
        return await self._get("/rate-limit-status", {"token": self.api_key})



NUB_API = NubApi(config.NUB_API_URL, config.NUB_API_KEY)

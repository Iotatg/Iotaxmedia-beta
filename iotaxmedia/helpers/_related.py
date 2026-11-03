# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""YouTube Music Radio Mix related-track engine.

Same approach nub-music-bot uses for its `get_related_suggestions`: hit
Innertube `music.youtube.com/youtubei/v1/next` with
`playlistId=RDAMVM{vid}` and `isAutomix=true`, then walk the response tree
for `playlistPanelVideoRenderer` / `compactVideoRenderer` entries. The
shared `related_tracks()` shim is what autoplay and the suggestion panel
both call — it always returns ``Track`` objects so callers don't have to
care whether the source was a radio mix or a YouTube search fallback.
"""

import re
from collections import deque

import aiohttp

from iotaxmedia import logger
from iotaxmedia.helpers import Track, utils as _utils

INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"

_http_session: aiohttp.ClientSession | None = None


def _get_http_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        _http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=15)
        )
    return _http_session
INNERTUBE_CLIENT_REMIX = {
    "clientName": "WEB_REMIX",
    "clientVersion": "1.20240101.01.00",
    "hl": "en",
    "gl": "US",
}
INNERTUBE_HEADERS_REMIX = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.youtube.com/",
}

YOUTUBE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


RECENT_PLAYED: dict[int, deque] = {}
_RECENT_MAX = 50


def _recent(chat_id: int) -> deque:
    return RECENT_PLAYED.setdefault(chat_id, deque(maxlen=_RECENT_MAX))


def note_played(chat_id: int, vidid, title: str = "") -> None:
    if vidid:
        _recent(chat_id).append(str(vidid))


def extract_vid(url_or_query: str) -> str | None:
    if not url_or_query:
        return None
    m = re.search(
        r"(?:v=|/shorts/|youtu\.be/|/embed/|/v/|/live/)([A-Za-z0-9_-]{11})",
        url_or_query,
    )
    if m:
        return m.group(1)
    s = str(url_or_query).strip()
    if YOUTUBE_ID_RE.fullmatch(s):
        return s
    return None


def _ytm_text(node) -> str:
    if isinstance(node, dict):
        return node.get("simpleText") or "".join(
            x.get("text", "") for x in node.get("runs", [])
        )
    return ""


def _extract_ytm_tracks(data: dict) -> list[dict]:
    tracks: list[dict] = []
    seen: set = set()

    def find_renderers(node):
        if isinstance(node, dict):
            renderer = None
            byline = None
            if "playlistPanelVideoRenderer" in node:
                renderer = node["playlistPanelVideoRenderer"]
                byline = renderer.get("shortBylineText") or renderer.get("longBylineText")
            elif "compactVideoRenderer" in node:
                renderer = node["compactVideoRenderer"]
                byline = renderer.get("shortBylineText") or renderer.get("ownerText")
            if renderer:
                vid = renderer.get("videoId")
                title = _ytm_text(renderer.get("title"))
                artist = _ytm_text(byline)
                dur = _ytm_text(renderer.get("lengthText"))
                thumbs = (renderer.get("thumbnail") or {}).get("thumbnails", [])
                thumb = thumbs[-1]["url"] if thumbs else ""
                if vid and title and vid not in seen:
                    seen.add(vid)
                    tracks.append(
                        {
                            "video_id": vid,
                            "title": title,
                            "artist": artist,
                            "duration": dur or "N/A",
                            "thumbnail": thumb,
                            "url": f"https://www.youtube.com/watch?v={vid}",
                        }
                    )
            for v in node.values():
                find_renderers(v)
        elif isinstance(node, list):
            for item in node:
                find_renderers(item)

    find_renderers(data)
    return tracks


async def get_related_suggestions(
    argument: str,
    limit: int = 5,
    exclude_ids: set | list | None = None,
    yt=None,
) -> list[dict]:
    """Fetch related-track suggestions for a video id / URL / title.

    Primary: Innertube ``music.youtube.com/.../next`` with ``RDAMVM{vid}``
    (YTM radio mix) — quota-free so the loop never silently drops.

    Last resort: ``yt.search_multi`` text search.

    ``exclude_ids`` is honoured first.
    """
    if not argument:
        return []
    vid = extract_vid(argument)
    if not vid and yt is not None:
        try:
            hit = await yt.search(query=argument, m_id=0, video=False)
            if hit and getattr(hit, "id", None):
                vid = hit.id
        except Exception:
            vid = None
    excluded: set = set(exclude_ids or [])
    if vid:
        excluded.add(vid)
    suggestions: list[dict] = []
    extracted: list[dict] = []


    if len(suggestions) < limit and vid:
        try:
            url = f"https://music.youtube.com/youtubei/v1/next?key={INNERTUBE_KEY}"
            body = {
                "context": {"client": INNERTUBE_CLIENT_REMIX},
                "videoId": vid,
                "playlistId": f"RDAMVM{vid}",
                "isAutomix": True,
            }
            async with _get_http_session().post(
                url, json=body, headers=INNERTUBE_HEADERS_REMIX
            ) as resp:
                if resp.status == 200:
                    ytm = _extract_ytm_tracks(await resp.json())
                    extracted.extend(ytm)
                    for t in ytm:
                        svid = t.get("video_id")
                        if (
                            svid
                            and svid not in excluded
                            and not any(
                                s.get("video_id") == svid for s in suggestions
                            )
                        ):
                            suggestions.append(t)
                            if len(suggestions) >= limit:
                                break
                    logger.info(
                        "[Suggest] YTM radio +%d for %s (total %d)",
                        len(ytm),
                        vid,
                        len(suggestions),
                    )
        except Exception as e:
            logger.warning("[Suggest] YTM radio failed for %s: %s", vid, e)

    if len(suggestions) < limit and yt is not None:
        try:
            query = argument if not vid else f"similar music to {vid}"
            tracks = await yt.search_multi(
                query=query, m_id=0, video=False, limit=limit * 3
            )
            for track in tracks or []:
                item_vid = getattr(track, "id", None)
                if (
                    item_vid
                    and item_vid not in excluded
                    and not any(s.get("video_id") == item_vid for s in suggestions)
                ):
                    suggestions.append(
                        {
                            "video_id": item_vid,
                            "title": getattr(track, "title", "N/A") or "N/A",
                            "artist": getattr(track, "channel_name", "N/A") or "N/A",
                            "duration": getattr(track, "duration", "N/A") or "N/A",
                            "thumbnail": getattr(track, "thumbnail", "") or "",
                            "url": getattr(track, "url", "")
                            or f"https://www.youtube.com/watch?v={item_vid}",
                        }
                    )
                    if len(suggestions) >= limit:
                        break
        except Exception as e:
            logger.warning("[Suggest] Fallback search failed: %s", e)
    if not suggestions and extracted and vid:
        suggestions = [t for t in extracted if t.get("video_id") != vid]
    return suggestions[:limit]


async def related_tracks(
    yt,
    current,
    chat_id: int | None = None,
    limit: int = 12,
    exclude_ids: set | None = None,
) -> list[Track]:
    """Return audio-only Tracks related to ``current`` (YTM radio mix).

    Always returns ``Track`` objects. Filters the finished track, duplicates
    and the in-memory recent-played deque. Never raises — returns ``[]`` on
    failure.
    """
    seed = ""
    if isinstance(current, Track):
        seed = current.id or current.title or ""
    else:
        seed = str(getattr(current, "id", "") or getattr(current, "title", "") or "")
    seen: set = set(_recent(chat_id)) if chat_id else set()
    if getattr(current, "id", None):
        seen.add(str(current.id))
    seen |= {str(x) for x in (exclude_ids or ())}
    raw = await get_related_suggestions(
        str(seed), limit=limit, exclude_ids=seen, yt=yt
    )
    out: list[Track] = []
    for item in raw or []:
        vid = item.get("video_id")
        if not vid:
            continue
        dur = item.get("duration") or "00:00"
        if dur == "N/A":
            dur = "00:00"
        out.append(
            Track(
                id=vid,
                channel_name=item.get("artist") or "",
                duration=dur,
                duration_sec=_utils.to_seconds(dur),
                title=(item.get("title") or "song")[:80],
                thumbnail=(item.get("thumbnail") or "").split("?")[0],
                url=item.get("url") or f"https://www.youtube.com/watch?v={vid}",
                video=False,
            )
        )
    return out

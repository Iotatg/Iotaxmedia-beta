# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
"""Clone customization value helpers and typed accessors.

Settings live in Mongo (source of truth) keyed per clone. Media values are
stored either as a legacy bare file_id string or a typed dict
``{"file_id": str, "type": str}`` so senders can dispatch correctly instead of
guessing from file_id prefixes.
"""

from typing import Any, Optional, List
import time

_MEDIA_TYPES = ("photo", "video", "animation", "document")

_chatbot_cache: dict[str, tuple[float, bool]] = {}
_CHATBOT_TTL = 20.0


def media_payload(file_id: str, media_type: Optional[str] = None) -> Any:
    """Build the storable value: a typed dict when possible, else bare string."""
    fid = str(file_id).strip() if file_id else ""
    if not fid:
        return None
    mtype = str(media_type or "").strip().lower()
    if mtype in _MEDIA_TYPES:
        return {"file_id": fid, "type": mtype}
    return fid


def parse_media(value: Any) -> tuple:
    """Normalize any stored media value into (media_type, file_id).

    ``media_type`` is None for legacy bare strings (senders then assume photo).
    """
    if not value:
        return None, None
    if isinstance(value, dict):
        fid = str(value.get("file_id") or "").strip() or None
        mtype = str(value.get("type") or "").strip().lower()
        return (mtype if mtype in _MEDIA_TYPES else None), fid
    fid = str(value).strip()
    return None, (fid or None)


def _store():
    """Resolve the process-wide CloneStore lazily (avoids import cycles)."""
    from iotaxmedia.clone.runtime import get_store

    return get_store()


async def current_media(setting_key: str):
    """(media_type, file_id) for THIS tree only when it is a clone.

    Detection reads the caller's OWN tree config: the hook serves each
    module copy its matching `config`, whose CLONE_TOKEN was shaped from
    env before that tree's package import. Main bot's config has no token.
    """
    from iotaxmedia import config

    token = getattr(config, "CLONE_TOKEN", None)
    if not token:
        return None, None
    value = await _store().get_setting(token, setting_key)
    return parse_media(value)



async def get_start_media(clone_id: str) -> Any:
    return await _store().get_setting(clone_id, "start_media")


async def set_start_media(clone_id: str, file_id: str, media_type=None) -> Any:
    payload = media_payload(file_id, media_type)
    return await _store().set_setting(clone_id, "start_media", payload)


async def del_start_media(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "start_media")


async def get_start_message(clone_id: str) -> Optional[str]:
    value = await _store().get_setting(clone_id, "start_message")
    return str(value) if value else None


async def set_start_message(clone_id: str, text: str) -> None:
    await _store().set_setting(clone_id, "start_message", text)


async def del_start_message(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "start_message")



async def get_ping_media(clone_id: str) -> Any:
    return await _store().get_setting(clone_id, "ping_media")


async def set_ping_media(clone_id: str, file_id: str, media_type=None) -> Any:
    payload = media_payload(file_id, media_type)
    return await _store().set_setting(clone_id, "ping_media", payload)


async def del_ping_media(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "ping_media")


async def get_stats_media(clone_id: str) -> Any:
    return await _store().get_setting(clone_id, "stats_media")


async def set_stats_media(clone_id: str, file_id: str, media_type=None) -> Any:
    payload = media_payload(file_id, media_type)
    return await _store().set_setting(clone_id, "stats_media", payload)


async def del_stats_media(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "stats_media")



async def get_clone_channel(clone_id: str) -> Optional[str]:
    value = await _store().get_setting(clone_id, "channel")
    return str(value) if value else None


async def set_clone_channel(clone_id: str, link: str) -> None:
    await _store().set_setting(clone_id, "channel", link.strip())


async def get_clone_support(clone_id: str) -> Optional[str]:
    value = await _store().get_setting(clone_id, "support")
    return str(value) if value else None


async def set_clone_support(clone_id: str, link: str) -> None:
    await _store().set_setting(clone_id, "support", link.strip())


async def get_clone_string(clone_id: str) -> Optional[str]:
    value = await _store().get_setting(clone_id, "string")
    return str(value) if value else None


async def set_clone_string(clone_id: str, session: str) -> bool:
    return bool(await _store().set_setting(clone_id, "string", session.strip()))


async def del_clone_string(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "string")


async def set_clone_mongo(clone_id: str, uri: str) -> bool:
    return bool(await _store().set_setting(clone_id, "mongo_uri", uri.strip()))


async def del_clone_mongo(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "mongo_uri")


async def get_clone_chatbot(clone_id: str) -> bool:
    item = _chatbot_cache.get(clone_id)
    if item and item[0] > time.time():
        return item[1]
    value = bool(await _store().get_setting(clone_id, "chatbot", False))
    _chatbot_cache[clone_id] = (time.time() + _CHATBOT_TTL, value)
    return value


async def set_clone_chatbot(clone_id: str, enabled: bool) -> None:
    await _store().set_setting(clone_id, "chatbot", bool(enabled))
    _chatbot_cache[clone_id] = (time.time() + _CHATBOT_TTL, bool(enabled))


async def get_clone_name(clone_id: str) -> Optional[str]:
    value = await _store().get_setting(clone_id, "bot_name")
    return str(value) if value else None


async def set_clone_name(clone_id: str, name: str) -> None:
    await _store().set_setting(clone_id, "bot_name", name.strip())


async def get_clone_logger(clone_id: str) -> Optional[int]:
    value = await _store().get_setting(clone_id, "logger_id")
    return int(value) if value else None


async def set_clone_logger(clone_id: str, chat_id) -> None:
    await _store().set_setting(clone_id, "logger_id", int(chat_id))


async def del_clone_logger(clone_id: str) -> None:
    await _store().del_setting(clone_id, "logger_id")


async def get_clone_channel_name(clone_id: str) -> Optional[str]:
    value = await _store().get_setting(clone_id, "channel_name")
    return str(value) if value else None


async def set_clone_channel_name(clone_id: str, name: str) -> None:
    await _store().set_setting(clone_id, "channel_name", name.strip())


async def del_clone_channel_name(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "channel_name")


async def get_clone_support_name(clone_id: str) -> Optional[str]:
    value = await _store().get_setting(clone_id, "support_name")
    return str(value) if value else None


async def set_clone_support_name(clone_id: str, name: str) -> None:
    await _store().set_setting(clone_id, "support_name", name.strip())


async def del_clone_support_name(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "support_name")


async def get_clone_owner_name(clone_id: str) -> Optional[str]:
    value = await _store().get_setting(clone_id, "owner_name")
    return str(value) if value else None


async def set_clone_owner_name(clone_id: str, name: str) -> None:
    await _store().set_setting(clone_id, "owner_name", name.strip())


async def del_clone_owner_name(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "owner_name")


_BTN_KEYS = ("help", "clone", "support", "channel", "owner", "language")


async def is_btn_enabled(clone_id: str, key: str) -> bool:
    value = await _store().get_setting(clone_id, f"btn_{key}", True)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "off", "no")


async def set_btn_enabled(clone_id: str, key: str, enabled: bool) -> None:
    await _store().set_setting(clone_id, f"btn_{key}", bool(enabled))


async def get_extra_buttons(clone_id: str) -> List[dict]:
    value = await _store().get_setting(clone_id, "extra_buttons", [])
    if isinstance(value, list):
        return [b for b in value if isinstance(b, dict) and b.get("name") and b.get("url")]
    return []


async def add_extra_button(clone_id: str, name: str, url: str) -> None:
    buttons = await get_extra_buttons(clone_id)
    name = name.strip()
    url = url.strip()
    buttons = [b for b in buttons if str(b.get("name", "")).lower() != name.lower()]
    buttons.append({"name": name[:32], "url": url[:256]})
    await _store().set_setting(clone_id, "extra_buttons", buttons[:12])


async def del_extra_button(clone_id: str, name: str) -> bool:
    buttons = await get_extra_buttons(clone_id)
    kept = [b for b in buttons if str(b.get("name", "")).lower() != name.strip().lower()]
    if len(kept) == len(buttons):
        return False
    await _store().set_setting(clone_id, "extra_buttons", kept)
    return True


async def clear_extra_buttons(clone_id: str) -> bool:
    return await _store().del_setting(clone_id, "extra_buttons")

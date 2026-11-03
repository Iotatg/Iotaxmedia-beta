# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import time

from pyrogram import enums, filters, types

from iotaxmedia import app, config, db, iotaxmedia, lang, logger, queue, yt
from iotaxmedia._fonts import stylish
from iotaxmedia.helpers import Track, buttons






SUGGESTIONS: dict[str, dict] = {}

SESSIONS: dict[int, dict] = {}

_SUGGEST_TTL = 1800
_SONG_STYLES = [
    enums.ButtonStyle.PRIMARY,
    enums.ButtonStyle.DANGER,
    enums.ButtonStyle.SUCCESS,
    enums.ButtonStyle.PRIMARY,
]


def _prune() -> None:
    now = time.time()
    expired = [k for k, v in SUGGESTIONS.items() if v["expire"] < now]
    for k in expired:
        SUGGESTIONS.pop(k, None)


def _truncate(text: str, max_len: int = 58) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"





async def get_related_songs(
    song_info: Track,
    limit: int = 4,
    chat_id: int | None = None,
    exclude: set | None = None,
) -> list[Track]:
    """Return up to ``limit`` related tracks for ``song_info``.

    Backed by the YouTube Music Radio Mix engine in
    ``helpers._related`` — same source YouTube itself shows in the
    "Up next" panel. Filters out the finished song, duplicate ids and
    anything already in ``exclude``. Never raises — returns ``[]`` on failure.
    """
    try:
        seed = (
            getattr(song_info, "id", None)
            or getattr(song_info, "title", "")
            or ""
        )
        if not seed:
            return []

        from iotaxmedia.helpers._related import RECENT_PLAYED, related_tracks

        seen: set = set(exclude or [])
        if chat_id:
            seen |= {str(v) for v in RECENT_PLAYED.get(chat_id, [])}

        raw = await related_tracks(
            yt,
            song_info,
            chat_id,
            limit=max(12, limit * 3),
            exclude_ids=seen,
        )
        if not raw:
            return []

        results: list[Track] = []
        for track in raw:
            if not track or not getattr(track, "id", None):
                continue
            if track.id == song_info.id:
                continue
            if track.id in seen:
                continue
            if any(r.id == track.id for r in results):
                continue
            results.append(track)
            seen.add(track.id)
            if len(results) >= limit:
                break
        return results
    except Exception as exc:
        logger.error(f"[suggest] get_related_songs failed: {exc}", exc_info=True)
        return []





def create_song_suggestion_buttons(songs: list[Track], chat_id: int) -> types.InlineKeyboardMarkup:
    """Build the 4 colored song buttons + a 'More Songs ?' button."""
    _prune()
    rows: list[list[types.InlineKeyboardButton]] = []
    for i, song in enumerate(songs[:4]):
        style = _SONG_STYLES[i % len(_SONG_STYLES)]
        label = f"🎵 {_truncate(song.title)}"
        SUGGESTIONS[song.id] = {"track": song, "expire": time.time() + _SUGGEST_TTL}
        rows.append(
            [
                buttons.ikb(
                    text=label,
                    style=style,
                    callback_data=f"suggest_play {song.id}",
                )
            ]
        )
    rows.append(
        [
            buttons.ikb(
                text="🟢 More Songs ?",
                style=enums.ButtonStyle.SUCCESS,
                callback_data="suggest_more 1",
            )
        ]
    )
    return types.InlineKeyboardMarkup(rows)


async def send_suggestions(chat_id: int, finished_song) -> None:
    """Send the 'You May Like' panel after a song+queue ends.

    Falls back to the styled ``queue_finished`` message when no related songs
    are available, so the end-of-queue notice is never duplicated with the
    suggestion panel.
    """
    try:
        if not isinstance(finished_song, Track):
            return



        from iotaxmedia.helpers._chat_owner import resolve_app as _resolve_app
        from iotaxmedia.helpers._related import note_played

        _bot = _resolve_app(chat_id)



        if finished_song.id:
            note_played(chat_id, finished_song.id, finished_song.title)

        songs = await get_related_songs(finished_song, limit=4, chat_id=chat_id)
        if not songs:
            _lang = await lang.get_lang(chat_id)
            await _bot.send_message(chat_id, stylish(_lang["queue_finished"]))
            return

        SESSIONS[chat_id] = {
            "finished": finished_song,
            "seen": {finished_song.id} | {s.id for s in songs},
            "page": 1,
        }
        text = stylish(
            "🎵 You May Like to Listen these tracks\n\n"
            "Choose a song below & I'll play it in this voice chat."
        )
        keyboard = create_song_suggestion_buttons(songs, chat_id)

        thumb_url = getattr(songs[0], "thumbnail", None)
        try:
            if thumb_url:
                await _bot.send_photo(
                    chat_id, photo=thumb_url, caption=text, reply_markup=keyboard
                )
            else:
                await _bot.send_message(chat_id, text, reply_markup=keyboard)
        except Exception:
            await _bot.send_message(chat_id, text, reply_markup=keyboard)
    except Exception as exc:
        logger.error(f"[suggest] send_suggestions failed: {exc}", exc_info=True)
        try:
            _lang = await lang.get_lang(chat_id)
            await app.send_message(chat_id, stylish(_lang["queue_finished"]))
        except Exception:
            pass





async def play_suggestion(chat_id: int, track: Track, user_mention: str):
    """Play the clicked suggested track now, reusing the existing loop.

    Always force-plays the exact track (by its YouTube id) as audio so it
    starts immediately and never hits "audio source not found". Returns
    ``(True, None)`` on success or ``(None, reason)`` on failure.
    """
    track.user = user_mention
    _lang = await lang.get_lang(chat_id)
    msg = await app.send_message(
        chat_id=chat_id, text=f"▶️ Playing: {track.title or 'Song'}"
    )



    track.video = False
    if not track.file_path:
        track.file_path = await yt.download(track.id, video=False)
    if not track.file_path:
        try:
            await msg.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
        except Exception:
            pass
        return None, "download_failed"

    track.message_id = msg.id


    try:
        from iotaxmedia.helpers._chat_owner import set_chat_owner

        set_chat_owner(chat_id, msg._client.id)
    except Exception:
        pass
    queue.force_add(chat_id, track)
    await iotaxmedia.play_media(chat_id=chat_id, message=msg, media=track)


    try:
        from iotaxmedia.helpers._related import note_played

        note_played(chat_id, track.id, track.title)
    except Exception:
        pass
    return True, None





@app.on_callback_query(filters.regex("^suggest_play ") & ~app.bl_users)
@lang.language()
async def suggest_play_cb(_, query: types.CallbackQuery):
    await query.answer()
    data = query.data.split()
    track_id = data[1] if len(data) > 1 else None
    chat_id = query.message.chat.id

    entry = SUGGESTIONS.pop(track_id, None) if track_id else None
    if not entry:
        try:
            await query.edit_message_text(stylish("🎵 This suggestion has expired."))
        except Exception:
            pass
        return

    track = entry["track"]
    current = queue.get_current(chat_id)
    if current and getattr(current, "id", None) == track.id:
        return await query.answer("Already playing", show_alert=True)

    try:
        played, info = await play_suggestion(chat_id, track, query.from_user.mention)
    except Exception as exc:
        logger.error(f"[suggest] play_suggestion failed: {exc}", exc_info=True)
        return await query.answer("Failed to play", show_alert=True)

    try:
        await query.message.delete()
    except Exception:
        pass

    if played is False:
        await query.answer(f"▶️ Queued: {track.title}", show_alert=True)
    elif played is True:
        await query.answer(f"▶️ Playing: {track.title}", show_alert=True)
    else:
        await query.answer("Song unavailable", show_alert=True)


@app.on_callback_query(filters.regex("^suggest_more ") & ~app.bl_users)
@lang.language()
async def suggest_more_cb(_, query: types.CallbackQuery):
    await query.answer()
    chat_id = query.message.chat.id
    session = SESSIONS.get(chat_id)
    if not session:
        try:
            await query.edit_message_text(
                stylish("🎵 This suggestion session has expired.")
            )
        except Exception:
            pass
        return

    session["page"] += 1
    songs = await get_related_songs(
        session["finished"], limit=4, chat_id=chat_id, exclude=session["seen"]
    )
    if not songs:
        try:
            await query.edit_message_text(
                stylish("🎵 More related songs are not available right now.")
            )
        except Exception:
            pass
        return

    session["seen"] |= {s.id for s in songs}
    keyboard = create_song_suggestion_buttons(songs, chat_id)
    try:
        await query.edit_message_reply_markup(reply_markup=keyboard)
    except Exception as exc:
        logger.error(f"[suggest] suggest_more edit failed: {exc}", exc_info=True)

# Authored By Iota Coders © 2025-2026
# SPDX-License-Identifier: MIT
import asyncio
import time
from collections import defaultdict

from ntgcalls import (
    ConnectionError,
    ConnectionNotFound,
    RTMPStreamingUnsupported,
    TelegramServerError,
)
from pyrogram.types import InputMediaPhoto, Message
from pytgcalls import PyTgCalls, exceptions, types
from pytgcalls.pytgcalls_session import PyTgCallsSession

from iotaxmedia import app, config, db, lang, logger, queue, thumb, userbot, yt
from iotaxmedia.helpers import Media, Track, buttons
from iotaxmedia.helpers._chat_owner import resolve_app
from iotaxmedia._fonts import stylish
from iotaxmedia.plugins.anonymous import ANON_NAME


class TgCall(PyTgCalls):
    def __init__(self):
        self.clients = []
        self.restarting = defaultdict(int)

    async def pause(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=True)

        media = queue.get_current(chat_id)
        if media and media.played_at:
            media.time += int(time.time() - media.played_at)
            media.played_at = None

        return await client.pause(chat_id)

    async def resume(self, chat_id: int) -> bool:
        client = await db.get_assistant(chat_id)
        await db.playing(chat_id, paused=False)

        media = queue.get_current(chat_id)
        if media:
            media.played_at = time.time()

        return await client.resume(chat_id)

    async def stop(self, chat_id: int) -> None:
        client = await db.get_assistant(chat_id)
        media = queue.get_current(chat_id)
        if media and media.message_id:
            try:
                await resolve_app(chat_id).delete_messages(chat_id, media.message_id)
            except Exception:
                pass
        queue.clear(chat_id)
        await db.remove_call(chat_id)
        await db.set_loop(chat_id, 0)

        try:
            await client.leave_call(chat_id, close=False)
        except Exception:
            pass

    async def play_media(
        self,
        chat_id: int,
        message: Message,
        media: Media | Track,
        seek_time: int = 0,
    ) -> None:
        self.restarting[chat_id] += 1
        if await db.get_call(chat_id):
            await asyncio.sleep(0.5)
        client = await db.get_assistant(chat_id)
        _lang = await lang.get_lang(chat_id)
        _thumb_mode = await db.get_thumb_mode(chat_id)
        _autoplay = await db.get_autoplay(chat_id)
        _thumb = (
            (
                await thumb.generate(media)
                if isinstance(media, Track)
                else config.DEFAULT_THUMB
            )
            if config.THUMB_GEN and _thumb_mode
            else None
        )

        if not media.file_path:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            return await self.play_next(chat_id)

        ffmpeg_params = (
            (f"-ss {seek_time}" if seek_time > 1 else "")
            + ("-vn" if not media.video else "")
        ).strip()

        stream = types.MediaStream(
            media_path=media.file_path,
            audio_parameters=types.AudioQuality.HIGH,
            video_parameters=types.VideoQuality.HD_720p,
            audio_flags=types.MediaStream.Flags.REQUIRED,
            video_flags=(
                types.MediaStream.Flags.AUTO_DETECT
                if media.video
                else types.MediaStream.Flags.IGNORE
            ),
            ffmpeg_parameters=ffmpeg_params or None,
        )

        try:
            if seek_time:
                await client.play(chat_id, stream)
            elif await db.get_call(chat_id):
                await client.play(chat_id, stream)
            else:
                await client.play(chat_id, stream)

            media.played_at = time.time()
            if seek_time:
                media.time = seek_time
            else:
                media.time = 1
                await db.add_call(chat_id)
                await db.note_play(chat_id)

                requester_id = getattr(media, "user_id", None)
                display_user = (
                    ANON_NAME
                    if requester_id and await db.is_anon(requester_id)
                    else media.user
                )
                text = _lang["play_media"].format(
                    media.url,
                    media.title,
                    media.duration,
                    display_user,
                )
                keyboard = buttons.controls(chat_id, lang=_lang, autoplay=_autoplay)
                try:
                    if _thumb:
                        await message.edit_media(
                            media=InputMediaPhoto(
                                media=_thumb,
                                caption=text,
                            ),
                            reply_markup=keyboard,
                        )
                    else:
                        await message.edit_text(text, reply_markup=keyboard)
                except Exception:
                    try:
                        await message.delete()
                    except Exception:
                        pass


                    _bot = resolve_app(chat_id)
                    try:
                        if _thumb:
                            sent = await _bot.send_photo(
                                chat_id=chat_id,
                                photo=_thumb,
                                caption=text,
                                reply_markup=keyboard,
                            )
                        else:
                            sent = await _bot.send_message(
                                chat_id=chat_id,
                                text=text,
                                reply_markup=keyboard,
                            )
                    except Exception:
                        sent = None
                    if sent is not None:
                        media.message_id = sent.id
        except FileNotFoundError:
            await message.edit_text(_lang["error_no_file"].format(config.SUPPORT_CHAT))
            await self.play_next(chat_id)
        except exceptions.NoActiveGroupCall:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_no_call"])
        except exceptions.NoAudioSourceFound:
            await message.edit_text(_lang["error_no_audio"])
            await self.play_next(chat_id)
        except (asyncio.TimeoutError, TimeoutError):
            await message.edit_text(_lang["error_tg_server"])
            await self.play_next(chat_id)
        except (ConnectionError, ConnectionNotFound, TelegramServerError):
            await self.stop(chat_id)
            await message.edit_text(_lang["error_tg_server"])
        except RTMPStreamingUnsupported:
            await self.stop(chat_id)
            await message.edit_text(_lang["error_rtmp"])
        finally:
            async def _dec():
                await asyncio.sleep(5)
                self.restarting[chat_id] -= 1

            asyncio.create_task(_dec())

    async def replay(self, chat_id: int) -> None:
        if not await db.get_call(chat_id):
            return

        media = queue.get_current(chat_id)
        _bot = resolve_app(chat_id)
        if media and media.message_id:
            try:
                await _bot.delete_messages(chat_id, media.message_id)
            except Exception:
                pass
        _lang = await lang.get_lang(chat_id)
        msg = await _bot.send_message(chat_id=chat_id, text=_lang["play_again"])
        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def play_next(self, chat_id: int, skip_user: str = None) -> None:


        _bot = resolve_app(chat_id)
        import logging as _logging

        _logging.getLogger(__name__).warning(
            f"[BETA-AUTOPLAY] chat={chat_id} routed via bot={getattr(_bot, 'id', '?')} "
            f"session={getattr(_bot, 'name', '?')}"
        )
        if loop := await db.get_loop(chat_id):
            await db.set_loop(chat_id, loop - 1)
            return await self.replay(chat_id)

        _lang = await lang.get_lang(chat_id)
        current = queue.get_current(chat_id)
        if current and current.message_id:
            try:
                await _bot.delete_messages(chat_id, current.message_id)
            except Exception:
                pass

        media = queue.get_next(chat_id, check=True)

        if not media:

            autoplay_enabled = await db.get_autoplay(chat_id)
            if autoplay_enabled and current and isinstance(current, Track):





                from iotaxmedia.helpers._related import note_played, related_tracks

                note_played(chat_id, current.id, current.title)
                tracks = await related_tracks(
                    yt, current, chat_id, limit=12, exclude_ids={current.id}
                )
                if tracks:

                    import random

                    media = random.choice(tracks)
                    media.video = False
                    media.user = stylish("autoplay") + " 🟢"
                    note_played(chat_id, media.id, media.title)
                else:

                    await self.stop(chat_id)

                    if skip_user:
                        await _bot.send_message(chat_id, _lang["play_skipped"].format(skip_user))





                    try:
                        from iotaxmedia.plugins.suggest import send_suggestions

                        if isinstance(current, Track):
                            asyncio.create_task(
                                send_suggestions(chat_id, current)
                            )
                    except Exception as exc:
                        logger.error(f"[suggest] hook failed: {exc}")
                    return
            else:

                await self.stop(chat_id)

                if skip_user:
                    await _bot.send_message(chat_id, _lang["play_skipped"].format(skip_user))





                try:
                    from iotaxmedia.plugins.suggest import send_suggestions

                    if isinstance(current, Track):
                        asyncio.create_task(
                            send_suggestions(chat_id, current)
                        )
                except Exception as exc:
                    logger.error(f"[suggest] hook failed: {exc}")
                return
        else:

            media = queue.get_next(chat_id)
            if not media:
                await self.stop(chat_id)
                return await _bot.send_message(chat_id, _lang["queue_finished"])

        msg = None
        if media.message_id:
            try:
                msg = await _bot.get_messages(chat_id, media.message_id)
                if not msg or not msg.id or msg.empty:
                    msg = None
                else:
                    try:
                        text = (
                            _lang["play_skipped"].format(skip_user)
                            + "\n\n"
                            + _lang["play_next"]
                            if skip_user
                            else _lang["play_next"]
                        )
                        await msg.edit_text(text)
                    except Exception:
                        pass
            except Exception:
                msg = None

        if not msg:
            text = (
                _lang["play_skipped"].format(skip_user) + "\n\n" + _lang["play_next"]
                if skip_user
                else _lang["play_next"]
            )
            try:
                msg = await _bot.send_message(chat_id=chat_id, text=text)
            except Exception:

                msg = await app.send_message(chat_id=chat_id, text=text)

        if not media.file_path:
            media.file_path = await yt.download(media.id, video=media.video)
            if not media.file_path:
                if msg:
                    try:
                        await msg.edit_text(
                            _lang["error_no_file"].format(config.SUPPORT_CHAT)
                        )
                    except Exception:
                        pass
                return await self.play_next(chat_id)

        media.message_id = msg.id
        await self.play_media(chat_id, msg, media)

    async def ping(self) -> float:
        pings = [client.ping for client in self.clients]
        return round(sum(pings) / len(pings), 2)

    async def _delete_msg(self, message: Message, delay: int = 2):
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except Exception:
            pass

    async def decorators(self, client: PyTgCalls) -> None:
        @client.on_update()
        async def update_handler(_, update: types.Update) -> None:
            if isinstance(update, types.UpdatedGroupCallParticipant):
                if not await db.get_vclogger(update.chat_id):
                    return
                try:
                    user = await app.get_users(update.participant.user_id)
                except Exception:
                    return

                _lang = await lang.get_lang(update.chat_id)
                if update.action == types.GroupCallParticipant.Action.JOINED:
                    text = _lang["vclog_joined"].format(user.mention, user.id)
                elif update.action == types.GroupCallParticipant.Action.LEFT:
                    text = _lang["vclog_left"].format(user.mention, user.id)
                else:
                    return

                try:
                    sent = await resolve_app(update.chat_id).send_message(
                        update.chat_id, text
                    )
                    asyncio.create_task(self._delete_msg(sent))
                except Exception:
                    pass

            elif isinstance(update, types.StreamEnded):
                if update.stream_type == types.StreamEnded.Type.AUDIO:
                    if self.restarting.get(update.chat_id):
                        return
                    await self.play_next(update.chat_id)
            elif isinstance(update, types.ChatUpdate):
                if update.status in [
                    types.ChatUpdate.Status.KICKED,
                    types.ChatUpdate.Status.LEFT_GROUP,
                    types.ChatUpdate.Status.CLOSED_VOICE_CHAT,
                ]:
                    await self.stop(update.chat_id)

    async def boot(self) -> None:
        PyTgCallsSession.notice_displayed = True
        for ub in userbot.clients:
            client = PyTgCalls(ub, cache_duration=100)
            await client.start()
            self.clients.append(client)
            await self.decorators(client)
        logger.info("PyTgCalls client(s) started.")

# iotaxmedia (beta)

A powerful Telegram music bot for group voice chats, supporting high-quality
audio and video streaming. This is the beta line of IotaXMedia, managed with
[uv](https://docs.astral.sh/uv/) and packaged as the `iotaxmedia` module.

- Version: 3.0.3
- Python: 3.12
- Streaming engine: Kurigram (Pyrogram) + PyTgCalls
- Downloads: `yt-dlp` with external API fallbacks

## Features

- High-quality audio and video playback in group voice chats
- Multiple assistant sessions for concurrent playback
- Clone bot support with per-clone customization
- Inline play-button controls for playback, seek, loop and autoplay
- Queue management, playlists, shuffle and skip
- Admin controls, authorization, broadcast and activity logging
- Optional AI-assisted replies (Apinex / OpenRouter)
- Multi-language user interface

## Requirements

- Python 3.12 (see `.python-version`)
- [uv](https://docs.astral.sh/uv/) for dependency management
- MongoDB database
- `API_ID` and `API_HASH` from https://my.telegram.org
- A bot token from [@BotFather](https://t.me/BotFather)
- Assistant `SESSION` string(s) for voice chat playback
- FFmpeg available on `PATH`

## Quick start

```bash
# Clone the repository
git clone https://github.com/Iotatg/Iota.git
cd Iota/iotaxmedia-beta

# Install uv, then sync dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Create your .env and set API_ID, API_HASH, BOT_TOKEN, MONGO_URL, SESSION, OWNER_ID

# Run the bot
bash start
# or directly:
uv run --no-sync python3 -m iotaxmedia
```

## Environment variables

Configuration is read from `.env` through `config.py`. The main variables:

| Variable | Required | Description |
| --- | --- | --- |
| `API_ID` | Yes | Telegram API ID from https://my.telegram.org |
| `API_HASH` | Yes | Telegram API hash from https://my.telegram.org |
| `BOT_TOKEN` | Yes | Bot token from @BotFather |
| `MONGO_URL` | Yes | MongoDB connection string |
| `OWNER_ID` | Yes | Numeric Telegram user ID of the owner |
| `SESSION` | Yes | Pyrogram assistant session for voice chat |
| `SESSION2` / `SESSION3` | No | Additional assistant sessions |
| `LOGGER_ID` | No | Group/channel ID for activity logs |
| `DURATION_LIMIT` | No | Maximum stream duration |
| `QUEUE_LIMIT` / `PLAYLIST_LIMIT` | No | Queue and playlist size limits |
| `CLONE_MODE` / `CLONE_TOKEN` | No | Enable and configure clone bots |
| `THUMB_GEN` / `VIDEO_PLAY` | No | Thumbnail generation and video playback toggles |
| `SUPPORT_CHAT` / `SUPPORT_CHANNEL` | No | Support links shown in the UI |
| `APINEX_API_KEY` / `OPENROUTER_API_KEY` | No | Optional AI reply providers |

## Commands

| Command | Description |
| --- | --- |
| `/play <query>` | Play a requested song or video |
| `/song <query>` | Download a song as an audio file |
| `/pause` | Pause the current stream |
| `/resume` | Resume the paused stream |
| `/skip` | Skip to the next track in the queue |
| `/stop` | Stop playback and clear the queue |
| `/queue` | Show the current queue |
| `/ping` | Check bot latency and system stats |
| `/settings` | Open the group settings panel |
| `/lang` | Change the interface language |
| `/clone` | Create your own clone bot |
| `/help` | Show the full command help |

Some commands require the bot to be an administrator in the chat.

## Project layout

```text
iotaxmedia/        Bot package (plugins, helpers, core, clone)
config.py          Configuration loader (reads .env)
pyproject.toml     Project metadata and dependencies
uv.lock            Locked dependency set
start              Launcher: `uv run --no-sync python3 -m iotaxmedia`
Dockerfile         Container image
.github/           Workflows, CODEOWNERS and repository metadata
```

## License

Released under the MIT License. See `LICENSE`.

Copyright (c) 2025-2026 Iota Coders.

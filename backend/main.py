import os
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from telethon import TelegramClient
from telethon.sessions import StringSession


# ============================================================
# CONFIG
# ============================================================

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = os.environ["TG_SESSION"]

CHANNEL_ID = int(
    os.getenv("TG_CHANNEL_ID", "-1002205337511")
)

START_MESSAGE_ID = int(
    os.getenv("TG_START_MESSAGE_ID", "1122")
)

EPISODE_COUNT = int(
    os.getenv("EPISODE_COUNT", "231")
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Beyblade Burst Telugu"
)

client = TelegramClient(
    StringSession(SESSION),
    API_ID,
    API_HASH
)


# ============================================================
# FRONTEND
# ============================================================

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(FRONTEND_DIR)),
        name="static"
    )


@app.get("/")
async def homepage():

    index_file = FRONTEND_DIR / "index.html"

    if not index_file.exists():
        return {
            "status": "online",
            "message": "Backend is running, but frontend/index.html was not found."
        }

    return FileResponse(
        str(index_file),
        media_type="text/html"
    )


@app.get("/app.js")
async def javascript():

    file = FRONTEND_DIR / "app.js"

    if not file.exists():
        raise HTTPException(
            404,
            "frontend/app.js not found"
        )

    return FileResponse(
        str(file),
        media_type="application/javascript"
    )


@app.get("/style.css")
async def stylesheet():

    file = FRONTEND_DIR / "style.css"

    if not file.exists():
        raise HTTPException(
            404,
            "frontend/style.css not found"
        )

    return FileResponse(
        str(file),
        media_type="text/css"
    )


# ============================================================
# TELEGRAM
# ============================================================

async def get_message(ep: int):

    if ep < 1 or ep > EPISODE_COUNT:
        raise HTTPException(
            404,
            "Episode not found"
        )

    message_id = START_MESSAGE_ID + ep - 1

    msg = await client.get_messages(
        CHANNEL_ID,
        ids=message_id
    )

    if not msg:
        raise HTTPException(
            404,
            "Telegram message not found"
        )

    if not msg.media:
        raise HTTPException(
            404,
            "Telegram message has no media"
        )

    return msg


# ============================================================
# GET VIDEO DURATION
# ============================================================

def get_video_duration(msg):

    """
    Telegram normally stores video duration inside
    DocumentAttributeVideo.

    Return seconds when available.
    """

    try:

        document = getattr(
            msg,
            "document",
            None
        )

        if not document:
            return None

        attributes = getattr(
            document,
            "attributes",
            []
        )

        for attribute in attributes:

            duration = getattr(
                attribute,
                "duration",
                None
            )

            if duration:
                return float(duration)

    except Exception:
        pass

    return None


# ============================================================
# HEALTH / INFO
# ============================================================

@app.get("/api/status")
async def status():

    return {
        "status": "online",
        "episodes": EPISODE_COUNT,
        "episode_1_message": START_MESSAGE_ID,
        "episode_231_message":
            START_MESSAGE_ID + EPISODE_COUNT - 1
    }


# ============================================================
# EPISODE INFORMATION
# ============================================================

@app.get("/api/episode/{ep}")
async def episode_info(ep: int):

    msg = await get_message(ep)

    file = msg.file

    if not file:
        raise HTTPException(
            404,
            "Message has no file"
        )

    duration = get_video_duration(msg)

    return {
        "episode": ep,
        "message_id": msg.id,
        "size": file.size,
        "name": file.name,
        "mime_type": file.mime_type or "video/mp4",
        "duration": duration
    }


# ============================================================
# VIDEO STREAM
# ============================================================

@app.get("/api/video/{ep}")
async def video(ep: int):

    msg = await get_message(ep)

    if not msg.file:
        raise HTTPException(
            404,
            "Message has no file"
        )

    duration = get_video_duration(msg)

    # --------------------------------------------------------
    # FFmpeg
    #
    # HEVC video is copied.
    # MP3 audio is converted to AAC.
    # MP4 is fragmented so it can start playing while
    # FFmpeg is still receiving the Telegram file.
    # --------------------------------------------------------

    ffmpeg_cmd = [
        "ffmpeg",

        "-hide_banner",
        "-loglevel",
        "error",

        "-i",
        "pipe:0",

        "-map",
        "0:v:0",

        "-map",
        "0:a:0?",

        "-c:v",
        "copy",

        "-c:a",
        "aac",

        "-b:a",
        "128k",

        "-movflags",
        "frag_keyframe+empty_moov+default_base_moof",

        "-f",
        "mp4",

        "pipe:1"
    ]

    process = await asyncio.create_subprocess_exec(
        *ffmpeg_cmd,

        stdin=asyncio.subprocess.PIPE,

        stdout=asyncio.subprocess.PIPE,

        stderr=asyncio.subprocess.PIPE
    )


    async def feed_telegram():

        try:

            async for chunk in client.iter_download(
                msg.media,
                chunk_size=1024 * 1024
            ):

                if process.stdin.is_closing():
                    break

                process.stdin.write(chunk)

                await process.stdin.drain()

        except Exception as error:

            print(
                "Telegram stream error:",
                error
            )

        finally:

            try:
                process.stdin.close()
            except Exception:
                pass


    async def stream_output():

        feeder = asyncio.create_task(
            feed_telegram()
        )

        try:

            while True:

                chunk = await process.stdout.read(
                    1024 * 256
                )

                if not chunk:
                    break

                yield chunk

        finally:

            if not feeder.done():
                feeder.cancel()

            try:
                await process.wait()
            except Exception:
                pass


    headers = {
        "Cache-Control": "no-cache",
        "Accept-Ranges": "none"
    }

    # If Telegram provided the duration, expose it
    # to the browser as metadata.
    if duration:
        headers["X-Video-Duration"] = str(duration)

    return StreamingResponse(
        stream_output(),
        media_type="video/mp4",
        headers=headers
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup():

    print("Connecting to Telegram...")

    await client.connect()

    authorized = await client.is_user_authorized()

    if not authorized:

        raise RuntimeError(
            "Telegram session is not authorized"
        )

    print(
        "Telegram connection successful."
    )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown():

    await client.disconnect()

    print(
        "Telegram connection closed."
            )

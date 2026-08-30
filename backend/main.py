import os
import re
import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
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

CHANNEL_ID = int(os.getenv("TG_CHANNEL_ID", "-1002205337511"))
START_MESSAGE_ID = int(os.getenv("TG_START_MESSAGE_ID", "1122"))
EPISODE_COUNT = int(os.getenv("EPISODE_COUNT", "231"))


# ============================================================
# APP
# ============================================================

app = FastAPI(title="Beyblade Burst Telugu")

client = TelegramClient(
    StringSession(SESSION),
    API_ID,
    API_HASH
)


# ============================================================
# FRONTEND DIRECTORY SEARCH
# ============================================================

# Search both same directory and parent directory to work on all cloud hosts
CURRENT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = CURRENT_DIR / "frontend"

if not FRONTEND_DIR.exists():
    FRONTEND_DIR = CURRENT_DIR.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
async def homepage():
    index_file = FRONTEND_DIR / "index.html"
    if not index_file.exists():
        return {
            "status": "online",
            "message": "Backend is running, but frontend/index.html was not found."
        }
    return FileResponse(str(index_file), media_type="text/html")


@app.get("/app.js")
async def javascript():
    file = FRONTEND_DIR / "app.js"
    if not file.exists():
        raise HTTPException(404, "frontend/app.js not found")
    return FileResponse(str(file), media_type="application/javascript")


@app.get("/style.css")
async def stylesheet():
    file = FRONTEND_DIR / "style.css"
    if not file.exists():
        raise HTTPException(404, "frontend/style.css not found")
    return FileResponse(str(file), media_type="text/css")


# ============================================================
# TELEGRAM HELPER
# ============================================================

async def get_message(ep: int):
    if ep < 1 or ep > EPISODE_COUNT:
        raise HTTPException(404, "Episode not found")

    message_id = START_MESSAGE_ID + ep - 1
    msg = await client.get_messages(CHANNEL_ID, ids=message_id)

    if not msg or not msg.media:
        raise HTTPException(404, "Telegram message or media not found")

    return msg


def get_video_duration(msg):
    try:
        document = getattr(msg, "document", None)
        if not document:
            return None
        for attribute in getattr(document, "attributes", []):
            duration = getattr(attribute, "duration", None)
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
        "episode_231_message": START_MESSAGE_ID + EPISODE_COUNT - 1
    }


@app.get("/api/episode/{ep}")
async def episode_info(ep: int):
    msg = await get_message(ep)
    file = msg.file

    if not file:
        raise HTTPException(404, "Message has no file")

    return {
        "episode": ep,
        "message_id": msg.id,
        "size": file.size,
        "name": file.name,
        "mime_type": file.mime_type or "video/mp4",
        "duration": get_video_duration(msg)
    }


# ============================================================
# OPTIMIZED VIDEO STREAMING (FAST SEEKING ENABLED)
# ============================================================

@app.get("/api/video/{ep}")
async def video(ep: int, request: Request):
    msg = await get_message(ep)

    if not msg.file:
        raise HTTPException(404, "Message has no file")

    file_size = msg.file.size
    range_header = request.headers.get("range")

    start = 0
    end = file_size - 1

    if range_header:
        match = re.search(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            if match.group(2):
                end = int(match.group(2))

    if start >= file_size:
        raise HTTPException(416, "Requested Range Not Satisfiable")

    # Serve small 5MB chunks to enable quick browser skipping
    max_chunk = 5 * 1024 * 1024
    end = min(end if (range_header and match and match.group(2)) else start + max_chunk - 1, file_size - 1)
    content_length = end - start + 1

    async def stream_telegram_chunks():
        try:
            # 1MB chunk size reduces round-trip API calls to Telegram
            async for chunk in client.iter_download(
                msg.media,
                offset=start,
                request_size=1024 * 1024,
                limit=content_length
            ):
                yield chunk
        except Exception as e:
            print(f"Streaming error on Ep {ep}: {e}")

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": msg.file.mime_type or "video/mp4",
        "Cache-Control": "public, max-age=3600",
    }

    duration = get_video_duration(msg)
    if duration:
        headers["X-Video-Duration"] = str(duration)

    return StreamingResponse(
        stream_telegram_chunks(),
        status_code=206 if range_header else 200,
        headers=headers
    )


# ============================================================
# STARTUP & SHUTDOWN
# ============================================================

@app.on_event("startup")
async def startup():
    print("Connecting to Telegram...")
    await client.connect()
    if not await client.is_user_authorized():
        raise RuntimeError("Telegram session is not authorized")
    print("Telegram connection successful.")


@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()
    print("Telegram connection closed.")
    

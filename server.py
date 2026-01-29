import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI()
@app.get("/")
def root():
    return {"status": "ok"}


# Allow access from anywhere (Android app, tunnel, browser)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hardened yt-dlp options (Windows + Tunnel safe)
YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "socket_timeout": 15,
    "retries": 5,

    # ✅ ANDROID CLIENT (CRITICAL FIX)
    "extractor_args": {
        "youtube": {
            "player_client": ["android"],
            "player_skip": ["webpage", "configs"],
        }
    },

    "http_headers": {
        "User-Agent": "com.google.android.youtube/18.11.34 (Linux; U; Android 13)",
        "Accept-Language": "en-US",
    },

    "format": "best",
}



@app.get("/api/stream/{video_id}")
async def get_stream(video_id: str):
    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, extract_info, url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def extract_info(url: str):
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)

    progressive_map = {}

    for f in info.get("formats", []):
        if (
            f.get("ext") == "mp4"
            and f.get("vcodec") != "none"
            and f.get("acodec") != "none"
        ):
            height = f.get("height")
            if height and height <= 1080:
                quality = f"{height}p"
                progressive_map[quality] = {
                    "quality": quality,
                    "mime": "video/mp4",
                    "url": f.get("url"),
                }

    if not progressive_map:
        raise Exception("No progressive MP4 streams found")

    # Sort qualities numerically (144p → 1080p)
    progressive = sorted(
        progressive_map.values(),
        key=lambda x: int(x["quality"].replace("p", ""))
    )

    return {
        "videoId": info.get("id"),
        "title": info.get("title"),
        "duration": int(info.get("duration", 0)),
        "streams": {
            "hls": None,
            "dash": None,
            "progressive": progressive,
            "audio": None,
        },
    }


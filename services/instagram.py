import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import yt_dlp
from groq import Groq
import instaloader


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
INSTAGRAM_COOKIE_BROWSER = os.getenv("INSTAGRAM_COOKIE_BROWSER", "edge")


def _safe_int(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _extract_hashtags(text: str) -> List[str]:
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


def _base_ydl_opts() -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
    }
    if INSTAGRAM_COOKIE_BROWSER:
        opts["cookiesfrombrowser"] = (INSTAGRAM_COOKIE_BROWSER,)
        print(f"[Instagram] Using cookies from browser: {INSTAGRAM_COOKIE_BROWSER}")
    return opts


def fetch_instagram_followers(username: str) -> int:
    if not username:
        return 0
    try:
        L = instaloader.Instaloader()
        profile = instaloader.Profile.from_username(L.context, username)
        print(f"[Instagram] Fetched followers for @{username}: {profile.followers}")
        return profile.followers
    except Exception as e:
        print(f"[Instagram] Follower fetch failed for @{username}: {e}")
        return 0


def fetch_instagram_metadata(url: str, video_id_label: str) -> Dict[str, Any]:
    print(f"[Instagram] Fetching metadata for {url}")

    ydl_opts = {
        **_base_ydl_opts(),
        "skip_download": True,
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    print(f"[Instagram] yt-dlp returned info for: {info.get('title', 'N/A')}")

    views    = _safe_int(info.get("view_count"))
    likes    = _safe_int(info.get("like_count"))
    comments = _safe_int(info.get("comment_count"))

    engagement_rate = round((likes + comments) / views * 100, 4) if views > 0 else 0.0

    description = info.get("description") or info.get("title") or ""
    tags = info.get("tags") or []
    tags_clean = [t if t.startswith("#") else f"#{t}" for t in tags]
    hashtags = list(dict.fromkeys(tags_clean + _extract_hashtags(description)))[:20]

    raw_date = info.get("upload_date", "")
    upload_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}" if len(raw_date) == 8 else "Unknown"

    uploader_id = (info.get("uploader_id") or info.get("channel_id") or "").lstrip("@")
    print(f"[Instagram] Fetching follower count for @{uploader_id}")
    followers = fetch_instagram_followers(uploader_id)

    meta = {
        "video_id":          video_id_label,
        "platform":          "instagram",
        "url":               url,
        "title":             description[:120] or "Instagram Reel",
        "creator":           info.get("uploader") or info.get("channel") or uploader_id or "Unknown",
        "views":             views,
        "likes":             likes,
        "comments":          comments,
        "followers":         followers,
        "hashtags":          hashtags,
        "upload_date":       upload_date,
        "duration":          int(info.get("duration") or 0),
        "engagement_rate":   engagement_rate,
        "transcript_chunks": 0,
    }
    print(f"[Instagram] Metadata: views={views}, likes={likes}, comments={comments}, followers={followers}")
    return meta


def fetch_instagram_transcript(url: str) -> str:
    print(f"[Instagram] Downloading audio for {url}")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_template = os.path.join(tmpdir, "audio.%(ext)s")

        ydl_opts = {
            **_base_ydl_opts(),
            "format": "bestaudio/best",
            "outtmpl": audio_template,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        audio_files = list(Path(tmpdir).glob("audio.*"))
        if not audio_files:
            raise ValueError(f"No audio file found after download for {url}")

        audio_path = audio_files[0]
        print(f"[Instagram] Audio downloaded: {audio_path.name} ({audio_path.stat().st_size} bytes)")

        print(f"[Instagram] Sending to Groq Whisper for transcription...")
        client = Groq(api_key=GROQ_API_KEY)
        with open(audio_path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=(audio_path.name, f),
                model="whisper-large-v3-turbo",
                response_format="text",
            )

        transcript_text = str(transcription).strip()
        print(f"[Instagram] Transcript ({len(transcript_text)} chars): {transcript_text[:200]}")
        return transcript_text

"""
instagram.py

Metadata  → instagrapi (free, unlimited, just needs IG login)
Transcript → yt-dlp audio-only + Groq Whisper API

instagrapi uses Instagram's private mobile API — same as the app.
Login once, session is cached to avoid logging in every request.
"""

import os
import re
import subprocess
import tempfile
from typing import Dict, Any, List

from instagrapi import Client
from groq import Groq

INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
SESSION_FILE       = "ig_session.json"   # cache session to avoid re-login every time

# ─── Singleton client — login once, reuse across requests ─────────────────────

_ig_client: Client | None = None

def get_ig_client() -> Client:
    """
    Returns a logged-in instagrapi Client.
    Loads cached session if available to avoid triggering login challenges.
    Session file persists across server restarts.
    """
    global _ig_client
    if _ig_client is not None:
        return _ig_client

    cl = Client()
    cl.delay_range = [1, 3]   # mimic human behavior, avoid rate limits

    if os.path.exists(SESSION_FILE):
        # Reuse saved session — no login challenge triggered
        print("[Instagram] Loading cached session from", SESSION_FILE)
        cl.load_settings(SESSION_FILE)
        # Login using cached session
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    else:
        print("[Instagram] Performing full login and creating session cache")
        # First time — full login + save session
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.dump_settings(SESSION_FILE)

    _ig_client = cl
    return cl


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_int(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0

def _extract_hashtags(text: str) -> List[str]:
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


# ─── Metadata via instagrapi ──────────────────────────────────────────────────

def fetch_instagram_metadata(url: str, video_id_label: str) -> Dict[str, Any]:
    """
    Uses instagrapi to fetch Reel metadata via Instagram's private mobile API.

    Flow:
      1. media_pk_from_url(url)  → extracts media PK from reel URL
      2. media_info(media_pk)    → full Media object with stats
      3. user_info(user_pk)      → follower count

    Media object fields used (confirmed from instagrapi docs):
      media.like_count       → likes (int)
      media.comment_count    → comments (int)
      media.play_count       → views for Reels (int, may be None)
      media.video_duration   → seconds (float)
      media.caption_text     → caption string
      media.taken_at         → datetime object
      media.user.pk          → user ID for follower lookup
      media.user.username    → @handle
      media.user.full_name   → display name
    """
    print(f"[Instagram] Fetching metadata for {url} via instagrapi")
    cl = get_ig_client()

    # Step 1: URL → media PK
    media_pk = cl.media_pk_from_url(url)

    # Step 2: media PK → full media info
    media = cl.media_info(media_pk)

    # Step 3: user PK → follower count
    user_info  = cl.user_info(media.user.pk)
    followers  = _safe_int(user_info.follower_count)

    # Views: Reels use play_count, fallback to view_count
    views    = _safe_int(getattr(media, "play_count", None) or
                         getattr(media, "view_count", None))
    likes    = _safe_int(media.like_count)
    comments = _safe_int(media.comment_count)

    engagement_rate = (
        round((likes + comments) / views * 100, 4) if views > 0 else 0.0
    )

    caption  = media.caption_text or ""
    hashtags = _extract_hashtags(caption)

    # taken_at is a datetime object → "YYYY-MM-DD"
    upload_date = (
        media.taken_at.strftime("%Y-%m-%d")
        if media.taken_at else "Unknown"
    )

    duration = int(getattr(media, "video_duration", 0) or 0)
    title    = caption[:120] or "Instagram Reel"

    print(f"[Instagram] Metadata: views={views}, likes={likes}, "
          f"comments={comments}, followers={followers}")

    return {
        "video_id":          video_id_label,
        "platform":          "instagram",
        "url":               url,
        "title":             title,
        "creator":           media.user.full_name or media.user.username,
        "views":             views,
        "likes":             likes,
        "comments":          comments,
        "followers":         followers,
        "hashtags":          hashtags,
        "upload_date":       upload_date,
        "duration":          duration,
        "engagement_rate":   engagement_rate,
        "transcript_chunks": 0,
    }


# ─── Transcript via yt-dlp audio + Groq Whisper ───────────────────────────────

def fetch_instagram_transcript(url: str) -> str:
    """
    yt-dlp downloads audio-only (~1-3MB for a 30s reel).
    Groq Whisper transcribes it — free: 7,200s audio/day.

    Fix for Windows cookie error: use --cookies-from-browser edge
    OR export cookies.txt once and pass --cookies cookies.txt
    """
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY not set in .env")

    print(f"[Instagram] Fetching transcript via yt-dlp and Groq Whisper")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_path = os.path.join(tmpdir, "audio.mp3")

        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            "--audio-quality", "worst",
            "--no-playlist",
            "--quiet",
            "-o", audio_path,
        ]

        # Fix Windows cookie database error
        # Option A (recommended): export cookies once to file
        cookies_file = "cookies.txt"
        if os.path.exists(cookies_file):
            print(f"[Instagram] Using local cookies file {cookies_file}")
            cmd += ["--cookies", cookies_file]
        else:
            # Option B: try browser cookies (may fail on Windows)
            browser = os.getenv("INSTAGRAM_COOKIE_BROWSER", "edge")
            print(f"[Instagram] Attempting to use browser cookies from {browser}")
            cmd += ["--cookies-from-browser", browser]

        cmd.append(url)

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=60
        )

        if result.returncode != 0 or not os.path.exists(audio_path):
            raise ValueError(
                f"yt-dlp audio download failed: {result.stderr[:300]}"
            )

        print(f"[Instagram] Audio: {os.path.getsize(audio_path)/1024/1024:.1f}MB")

        groq_client = Groq(api_key=GROQ_API_KEY)
        with open(audio_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=("audio.mp3", f),
                model="whisper-large-v3-turbo",
                response_format="text",
            )

        text = str(transcription).strip()
        print(f"[Instagram] Transcript: {len(text)} chars")
        return text

"""
Instagram Reel: metadata, followers, and transcript extraction.

Architecture:
  Metadata   → yt-dlp --cookies --dump-json  (authenticated = gets views)
  Followers  → Instagram Web API with cookies (authenticated)
  Transcript → yt-dlp --cookies -x --audio-format mp3 + Groq Whisper
  Fallback   → yt-dlp without cookies (unauthenticated, limited data)

Cookie flow:
  1. User runs  python export_ig_cookies.py  locally (one-time)
  2. This exports Edge browser cookies to  ig_cookies.txt
  3. Docker mounts ig_cookies.txt → backend uses it for all yt-dlp calls
"""
import os
import re
import json
import subprocess
import tempfile
import glob
from typing import Dict, Any, List
from http.cookiejar import MozillaCookieJar

import httpx
from groq import Groq

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
IG_COOKIES_FILE = os.getenv("IG_COOKIES_FILE", "ig_cookies.txt")


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe_int(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _extract_hashtags(text: str) -> List[str]:
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


def _has_cookies() -> bool:
    """Check if a valid cookie file exists."""
    return os.path.exists(IG_COOKIES_FILE) and os.path.getsize(IG_COOKIES_FILE) > 50


def _ytdlp_base_args() -> List[str]:
    """Return base yt-dlp args, including --cookies if available."""
    args = ["yt-dlp"]
    if _has_cookies():
        args.extend(["--cookies", IG_COOKIES_FILE])
    return args


# ── Follower count via Instagram Web API (with cookies) ──────────────────────

def _fetch_follower_count(creator_username: str) -> int:
    """
    Fetch follower count using Instagram's web_profile_info API.
    Requires valid session cookies exported from the browser.
    Returns 0 if cookies are missing or request fails.
    """
    if not _has_cookies() or not creator_username:
        return 0

    try:
        # Parse cookies from Netscape cookie file
        jar = MozillaCookieJar(IG_COOKIES_FILE)
        jar.load(ignore_discard=True, ignore_expires=True)

        # Build cookie header string
        cookie_str = "; ".join(f"{c.name}={c.value}" for c in jar if ".instagram.com" in (c.domain or ""))
        
        # Extract csrftoken
        csrf = ""
        for c in jar:
            if c.name == "csrftoken":
                csrf = c.value
                break

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
            "Cookie": cookie_str,
            "X-CSRFToken": csrf,
            "X-IG-App-ID": "936619743392459",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": f"https://www.instagram.com/{creator_username}/",
        }

        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(
                f"https://i.instagram.com/api/v1/users/web_profile_info/?username={creator_username}",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                followers = data.get("data", {}).get("user", {}).get("edge_followed_by", {}).get("count", 0)
                if followers:
                    print(f"[Instagram] Followers for @{creator_username}: {followers:,}")
                    return followers
    except Exception as e:
        print(f"[Instagram] Follower fetch failed for @{creator_username}: {e}")

    return 0


# ── Metadata via yt-dlp (with cookies for authenticated access) ──────────────

def fetch_instagram_metadata(url: str, video_id_label: str) -> Dict[str, Any]:
    """
    Fetches Instagram Reel metadata using yt-dlp.
    If ig_cookies.txt exists, uses authenticated access (gets views, better data).
    Falls back to unauthenticated yt-dlp if cookies are missing.
    """
    auth_mode = "authenticated" if _has_cookies() else "unauthenticated"
    print(f"[Instagram] Fetching metadata for {url} via yt-dlp ({auth_mode})")

    cmd = _ytdlp_base_args() + [
        "--dump-json",
        "--no-playlist",
        "--quiet",
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ValueError(f"yt-dlp metadata extraction failed: {stderr}")

    raw_lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
    if not raw_lines:
        raise ValueError("yt-dlp returned no JSON output")

    info: Dict[str, Any] = json.loads(raw_lines[0])

    # ── parse fields ──
    caption: str = info.get("description") or info.get("title") or ""
    creator: str = (
        info.get("uploader")
        or info.get("uploader_id")
        or info.get("channel")
        or "Unknown"
    )
    # Extract username for follower lookup (yt-dlp provides uploader_id as username)
    creator_username: str = info.get("uploader_id") or info.get("channel_id") or ""

    views: int = _safe_int(info.get("view_count")) or _safe_int(info.get("play_count")) or 0
    likes: int = _safe_int(info.get("like_count"))
    comments: int = _safe_int(info.get("comment_count"))
    duration: int = int(info.get("duration") or 0)

    raw_date: str = str(info.get("upload_date") or "")
    upload_date: str = (
        f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        if len(raw_date) == 8
        else "Unknown"
    )

    title: str = caption[:120] or "Instagram Reel"
    hashtags: List[str] = list(dict.fromkeys(
        [f"#{t}" for t in (info.get("tags") or [])]
        + _extract_hashtags(caption)
    ))[:20]

    # ── fetch followers (authenticated only) ──
    followers: int = _fetch_follower_count(creator_username)

    # engagement rate — guard against views=0
    engagement_rate: float = (
        round((likes + comments) / views * 100, 4) if views > 0 else 0.0
    )

    print(
        f"[Instagram] Metadata ({auth_mode}): views={views}, likes={likes}, "
        f"comments={comments}, followers={followers}, engagement_rate={engagement_rate}"
    )

    return {
        "video_id":          video_id_label,
        "platform":          "instagram",
        "url":               url,
        "title":             title,
        "creator":           creator,
        "views":             views,
        "likes":             likes,
        "comments":          comments,
        "followers":         followers,
        "hashtags":          hashtags,
        "upload_date":       upload_date,
        "duration":          duration,
        "engagement_rate":   engagement_rate,
        "transcript_chunks": 0,
        "video_url":         url,
    }


# ── Transcript via yt-dlp + Groq Whisper ─────────────────────────────────────

def fetch_instagram_transcript(video_url: str) -> str:
    """
    Downloads audio from Instagram Reel using yt-dlp (with cookies if available).
    Extracts audio via FFmpeg → sends to Groq Whisper for transcription.
    """
    if not video_url:
        raise ValueError("No video URL provided for transcript")

    auth_mode = "authenticated" if _has_cookies() else "unauthenticated"
    print(f"[Instagram] Downloading audio via yt-dlp ({auth_mode})")

    with tempfile.TemporaryDirectory() as tmpdir:
        out_template = os.path.join(tmpdir, "media.%(ext)s")

        cmd = _ytdlp_base_args() + [
            "-x", "--audio-format", "mp3",
            "--no-playlist",
            "--no-post-overwrites",
            "--quiet",
            "-o", out_template,
            video_url,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        downloaded_files = glob.glob(os.path.join(tmpdir, "media.*"))

        if result.returncode != 0 or not downloaded_files:
            stderr = result.stderr.strip()
            print(f"[Instagram] yt-dlp download failed: {stderr}")
            # Fallback: direct HTTP download of video file
            return _direct_download_transcribe(video_url, tmpdir)

        media_path = downloaded_files[0]
        filename = os.path.basename(media_path)
        size_mb = os.path.getsize(media_path) / 1024 / 1024
        print(f"[Instagram] Media ready: {filename} ({size_mb:.1f} MB)")

        return _transcribe_file(media_path, filename)


def _direct_download_transcribe(video_url: str, tmpdir: str) -> str:
    """Fallback: download video via httpx, extract audio with ffmpeg, then transcribe."""
    print(f"[Instagram] Fallback: downloading via httpx + ffmpeg audio extraction")
    video_path = os.path.join(tmpdir, "reel.mp4")
    audio_path = os.path.join(tmpdir, "reel.mp3")

    with httpx.Client(timeout=60, follow_redirects=True) as client:
        resp = client.get(video_url)
        if resp.status_code != 200:
            raise ValueError(f"Direct download failed: HTTP {resp.status_code}")
        with open(video_path, "wb") as f:
            f.write(resp.content)

    size_mb = os.path.getsize(video_path) / 1024 / 1024
    print(f"[Instagram] Downloaded: {size_mb:.1f} MB")

    # Extract audio with ffmpeg (available in Docker)
    ffmpeg_result = subprocess.run(
        ["ffmpeg", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-q:a", "4", "-y", audio_path],
        capture_output=True, text=True, timeout=60,
    )

    if ffmpeg_result.returncode == 0 and os.path.exists(audio_path) and os.path.getsize(audio_path) > 0:
        print(f"[Instagram] Audio extracted: {os.path.getsize(audio_path) / 1024:.0f} KB")
        return _transcribe_file(audio_path, "reel.mp3")

    # If ffmpeg failed, try sending the raw video file — Whisper sometimes accepts mp4
    print(f"[Instagram] ffmpeg extraction failed, trying raw video with Whisper")
    return _transcribe_file(video_path, "reel.mp4")


def _transcribe_file(file_path: str, filename: str) -> str:
    """Send file to Groq Whisper API and return transcript text."""
    groq_client = Groq(api_key=GROQ_API_KEY)
    with open(file_path, "rb") as f:
        transcription = groq_client.audio.transcriptions.create(
            file=(filename, f),
            model="whisper-large-v3-turbo",
            response_format="text",
        )
    text = str(transcription).strip()
    print(f"[Instagram] Transcript: {len(text)} chars")
    return text
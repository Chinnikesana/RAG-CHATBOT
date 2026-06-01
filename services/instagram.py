"""
Metadata  -> instagrapi (free, unlimited, just needs IG login)
Transcript -> yt-dlp audio-only + Groq Whisper API
"""
import httpx


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


_ig_client: Client | None = None

def get_ig_client() -> Client:
 
    global _ig_client
    if _ig_client is not None:
        return _ig_client

    cl = Client()
    cl.delay_range = [1, 3]  

    if os.path.exists(SESSION_FILE):
        print("[Instagram] Loading cached session from", SESSION_FILE)
        cl.load_settings(SESSION_FILE)
     
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
    else:
        print("[Instagram] Performing full login and creating session")
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.dump_settings(SESSION_FILE)

    _ig_client = cl
    return cl


#  Helpers fns

def _safe_int(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0

def _extract_hashtags(text: str) -> List[str]:
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


# getting Metadata via instagrapi

def fetch_instagram_metadata(url: str, video_id_label: str) -> Dict[str, Any]:
    """
    use  private mobile API (_v1 methods) for metadata.
 
    """
    print(f"[Instagram] Fetching metadata for {url} via instagrapi")
    cl = get_ig_client()
    media_pk = cl.media_pk_from_url(url)

    media = cl.media_info_v1(media_pk)
  #for getting user info
    user  = cl.user_info_v1(media.user.pk)
    followers = _safe_int(user.follower_count)

    views    = _safe_int(getattr(media, "play_count", None) or
                         getattr(media, "view_count", None))
    likes    = _safe_int(media.like_count)
    comments = _safe_int(media.comment_count)

    engagement_rate = (
        round((likes + comments) / views * 100, 4) if views > 0 else 0.0
    )

    caption     = media.caption_text or ""
    hashtags    = _extract_hashtags(caption)
    upload_date = (
        media.taken_at.strftime("%Y-%m-%d") if media.taken_at else "Unknown"
    )
    duration = int(getattr(media, "video_duration", 0) or 0)
    title    = caption[:120] or "Instagram Reel"

    print(f"[Instagram] Metadata: views={views}, likes={likes}, "
          f"comments={comments}, followers={followers}, "
          f"engagement_rate={engagement_rate}, hashtags={hashtags}, "
          f"upload_date={upload_date}, duration={duration}, "
          f"title='{title}', creator='{user.full_name or media.user.username}'")

    return {
        "video_id":          video_id_label,
        "platform":          "instagram",
        "url":               url,
        "title":             title,
        "creator":           user.full_name or media.user.username,
        "views":             views,
        "likes":             likes,
        "comments":          comments,
        "followers":         followers,
        "hashtags":          hashtags,
        "upload_date":       upload_date,
        "duration":          duration,
        "engagement_rate":   engagement_rate,
        "transcript_chunks": 0,
         "video_url": str(media.video_url)
    }
# # Transcript via yt-dlp audio + Groq Whisper 


def fetch_instagram_transcript(video_url: str) -> str:
    """
    Takes direct CDN video URL and downloads native audio format, bypassing FFmpeg.
    Transcribes using Groq Whisper API.
    """
    if not video_url:
        raise ValueError("No video URL provided")

    print(f"[Instagram] Downloading native audio from CDN URL directly")

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_template = os.path.join(tmpdir, "audio.%(ext)s")

        result = subprocess.run(
            [
                "yt-dlp",
              
                 "--audio-quality", "worst",
                "--no-playlist",
                "--quiet",
                "-o", audio_template,
                video_url,           
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        import glob
        downloaded_files = glob.glob(os.path.join(tmpdir, "audio.*"))

        if result.returncode != 0 or not downloaded_files:
            print(f"[Instagram] Audio extraction failed or no audio files found, falling back.")
            return _download_and_transcribe(video_url)

        audio_path = downloaded_files[0]
        filename = os.path.basename(audio_path)
        print(f"[Instagram] Audio {filename}: {os.path.getsize(audio_path)/1024/1024:.1f}MB")

        groq_client = Groq(api_key=GROQ_API_KEY)
        with open(audio_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=(filename, f),
                model="whisper-large-v3-turbo",
                response_format="text",
            )

        text = str(transcription).strip()
      
        print(f"[Instagram] Transcript fetched successfully: {len(text)} chars")
        return text

def _download_and_transcribe(video_url: str) -> str:
    """
    Fallback
    """
    import httpx

    print(f"[Instagram] Downloading video directly via httpx")

    with tempfile.TemporaryDirectory() as tmpdir:
        video_path = os.path.join(tmpdir, "reel.mp4")

        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(video_url)
            if resp.status_code != 200:
                raise ValueError(f"Direct download failed: {resp.status_code}")
            with open(video_path, "wb") as f:
                f.write(resp.content)

        size_mb = os.path.getsize(video_path) / 1024 / 1024
        print(f"[Instagram] Video downloaded: {size_mb:.1f}MB")

        groq_client = Groq(api_key=GROQ_API_KEY)
        with open(video_path, "rb") as f:
            transcription = groq_client.audio.transcriptions.create(
                file=("reel.mp4", f),
                model="whisper-large-v3-turbo",
                response_format="text",
            )

        text = str(transcription).strip()
        print(f"[Instagram] Transcript: {len(text)} chars")
        return text
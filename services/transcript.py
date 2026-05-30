"""
transcript.py
Extracts transcripts from YouTube and Instagram Reels using yt-dlp.
Falls back to faster-whisper for audio transcription when subtitles are unavailable.
"""

import os
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import yt_dlp

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    YT_TRANSCRIPT_API_AVAILABLE = True
except ImportError:
    YT_TRANSCRIPT_API_AVAILABLE = False


def _extract_youtube_id(url: str) -> Optional[str]:
    """Pull video ID from any YouTube URL format."""
    patterns = [
        r"(?:v=|youtu\.be/|shorts/)([A-Za-z0-9_-]{11})",
        r"embed/([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


def _is_instagram(url: str) -> bool:
    return "instagram.com" in url


def get_youtube_transcript(url: str) -> str:
    """
    Try youtube-transcript-api first (instant, no download).
    Fall back to yt-dlp subtitle extraction.
    """
    video_id = _extract_youtube_id(url)

    if YT_TRANSCRIPT_API_AVAILABLE and video_id:
        try:
            entries = YouTubeTranscriptApi.get_transcript(video_id)
            transcript = " ".join(e["text"] for e in entries)
            if transcript.strip():
                return transcript.strip()
        except Exception:
            pass

    return _get_transcript_via_ytdlp(url)


def get_instagram_transcript(url: str) -> str:
    """
    Instagram Reels: try auto-subtitles via yt-dlp, fall back to Whisper.
    """
    return _get_transcript_via_ytdlp(url, try_whisper_fallback=True)


def _get_transcript_via_ytdlp(url: str, try_whisper_fallback: bool = False) -> str:
    """
    Downloads subtitles with yt-dlp. If none found and try_whisper_fallback is True,
    downloads audio and transcribes with faster-whisper.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_template = os.path.join(tmpdir, "%(id)s")

        ydl_opts = {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "vtt",
            "skip_download": True,
            "outtmpl": output_template,
            "quiet": True,
            "no_warnings": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
            except Exception:
                pass

        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if vtt_files:
            return _parse_vtt(vtt_files[0])

        if try_whisper_fallback:
            return _whisper_transcribe(url, tmpdir)

    return "[Transcript unavailable]"


def _parse_vtt(vtt_path: Path) -> str:
    """Parse a WebVTT file into plain text, deduplicated."""
    text = vtt_path.read_text(encoding="utf-8", errors="replace")
    lines = []
    seen = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or "-->" in line:
            continue
        # Strip HTML tags
        line = re.sub(r"<[^>]+>", "", line)
        if line and line not in seen:
            seen.add(line)
            lines.append(line)
    return " ".join(lines)


def _whisper_transcribe(url: str, tmpdir: str) -> str:
    """
    Download audio with yt-dlp then transcribe with faster-whisper (base model, CPU).
    """
    audio_path = os.path.join(tmpdir, "audio.mp3")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": audio_path,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "128",
        }],
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([url])
        except Exception:
            return "[Transcript unavailable]"

    # Find downloaded audio file
    audio_files = list(Path(tmpdir).glob("*.mp3")) + list(Path(tmpdir).glob("*.m4a"))
    if not audio_files:
        return "[Transcript unavailable]"

    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("base", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(audio_files[0]), beam_size=5)
        return " ".join(seg.text.strip() for seg in segments)
    except ImportError:
        return "[Whisper not installed – pip install faster-whisper]"
    except Exception as e:
        return f"[Whisper error: {str(e)}]"


def extract_transcript(url: str) -> str:
    """Main entry point. Detects platform and routes accordingly."""
    if _is_youtube(url):
        return get_youtube_transcript(url)
    elif _is_instagram(url):
        return get_instagram_transcript(url)
    else:
        # Generic: try yt-dlp subtitle extraction for other platforms
        return _get_transcript_via_ytdlp(url, try_whisper_fallback=True)

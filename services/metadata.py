"""
metadata.py
Extracts structured metadata from YouTube and Instagram videos using yt-dlp.
Computes engagement rate = (likes + comments) / views * 100.
"""

import re
from typing import Dict, Any, List, Optional

import yt_dlp


def _safe_int(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _extract_hashtags(text: str) -> List[str]:
    """Pull #hashtags from title/description."""
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


def _format_date(date_str: Optional[str]) -> str:
    """Convert YYYYMMDD → YYYY-MM-DD."""
    if not date_str:
        return "Unknown"
    if len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str


def fetch_video_metadata(url: str, video_id: str) -> Dict[str, Any]:
    """
    Use yt-dlp to extract metadata for any supported platform.
    Returns a standardised dict ready to become VideoMetadata.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    views    = _safe_int(info.get("view_count"))
    likes    = _safe_int(info.get("like_count"))
    comments = _safe_int(info.get("comment_count"))
    followers = _safe_int(
        info.get("channel_follower_count")
        or info.get("uploader_follower_count")
        or info.get("uploader_subscriber_count")
    )

    # Engagement rate — guard against division by zero
    engagement_rate = round((likes + comments) / views * 100, 4) if views > 0 else 0.0

    # Hashtags from tags list + description
    tags = info.get("tags") or []
    desc = info.get("description") or ""
    title = info.get("title") or "Unknown"
    hashtags = list(dict.fromkeys(
        [f"#{t}" for t in tags if t] + _extract_hashtags(desc) + _extract_hashtags(title)
    ))[:20]  # cap at 20

    # Platform detection
    webpage_url = info.get("webpage_url", url)
    if "youtube.com" in webpage_url or "youtu.be" in webpage_url:
        platform = "youtube"
    elif "instagram.com" in webpage_url:
        platform = "instagram"
    else:
        platform = info.get("extractor_key", "unknown").lower()

    return {
        "video_id": video_id,
        "platform": platform,
        "url": url,
        "title": title,
        "creator": info.get("uploader") or info.get("channel") or "Unknown",
        "views": views,
        "likes": likes,
        "comments": comments,
        "followers": followers,
        "hashtags": hashtags,
        "upload_date": _format_date(info.get("upload_date")),
        "duration": _safe_int(info.get("duration")),
        "engagement_rate": engagement_rate,
        "transcript_chunks": 0,  # filled in after chunking
    }

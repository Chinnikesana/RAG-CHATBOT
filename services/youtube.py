"""
youtube.py
Handles all YouTube video processing:
  - Metadata via YouTube Data API v3 (fast, structured, free 10K req/day)
  - Transcript via youtube-transcript-api (free, no key needed)

Official API docs: https://developers.google.com/youtube/v3/docs/videos
Response shape confirmed from Google docs:
  item.snippet        → title, channelTitle, channelId, publishedAt, tags, description
  item.statistics     → viewCount, likeCount, commentCount (all returned as STRINGS)
  item.contentDetails → duration (ISO 8601 string e.g. "PT1M30S")
  channel.statistics  → subscriberCount (string)
"""

import os
import re
import isodate
from typing import Dict, Any, List
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")



def extract_video_id(url: str) -> str:
    """
    Extracts the 11-character YouTube video ID from any YouTube URL format.
    Supports: watch?v=, youtu.be/, /shorts/, /embed/
    """
    patterns = [r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract YouTube video ID from URL: {url}")


def _parse_duration(iso_duration: str) -> int:
    """
    Convert ISO 8601 duration (e.g. PT1M30S) to total seconds.
    YouTube API returns contentDetails.duration in this format.
    """
    try:
        return int(isodate.parse_duration(iso_duration).total_seconds())
    except Exception:
        return 0


def _extract_hashtags(text: str) -> List[str]:
    """Extract #hashtags from title or description text."""
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


def _safe_int(val) -> int:
    """
    YouTube API returns ALL statistics fields as strings, not integers.
    e.g. statistics.viewCount = "1234567" (string)
    This safely converts to int regardless of input type.
    """
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


# Core Functions

def fetch_youtube_metadata(url: str, video_id_label: str) -> Dict[str, Any]:
    """
    Fetches video metadata using YouTube Data API v3.
    """
    vid = extract_video_id(url)
    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    video_resp = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=vid
    ).execute()

    if not video_resp.get("items"):
        raise ValueError(f"YouTube video not found: {url}")

    item         = video_resp["items"][0]
    snippet      = item["snippet"]                   
    stats        = item.get("statistics", {})         
    content      = item["contentDetails"]             #

    views    = _safe_int(stats.get("viewCount"))
    likes    = _safe_int(stats.get("likeCount"))
    comments = _safe_int(stats.get("commentCount"))

    engagement_rate = (
        round((likes + comments) / views * 100, 4) if views > 0 else 0.0
    )

    channel_id = snippet.get("channelId", "")
    followers = 0
    if channel_id:
        ch_resp = youtube.channels().list(
            part="statistics",
            id=channel_id
        ).execute()
        if ch_resp.get("items"):
            followers = _safe_int(
                ch_resp["items"][0].get("statistics", {}).get("subscriberCount", 0)
            )

    tags        = snippet.get("tags") or []         
    description = snippet.get("description") or ""
    title       = snippet.get("title") or "Unknown"

    hashtags = list(dict.fromkeys(
        [f"#{t}" for t in tags]
        + _extract_hashtags(description)
        + _extract_hashtags(title)
    ))[:20]

    raw_date    = snippet.get("publishedAt", "")
    upload_date = raw_date[:10] if raw_date else "Unknown"

    return {
        "video_id":        video_id_label,
        "platform":        "youtube",
        "url":             url,
        "title":           title,
        "creator":         snippet.get("channelTitle") or "Unknown",
        "views":           views,
        "likes":           likes,
        "comments":        comments,
        "followers":       followers,
        "hashtags":        hashtags,
        "upload_date":     upload_date,
        "duration":        _parse_duration(content.get("duration", "PT0S")),
        "engagement_rate": engagement_rate,
        "transcript_chunks": 0,  # filled after chunking in ingest.py
    }


def fetch_youtube_transcript(url: str) -> str:
    """
    Fetches transcriptyoutube-transcript-api.
 
    """
    vid = extract_video_id(url)
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(vid)

        try:
            transcript = transcript_list.find_manually_created_transcript(["en"])
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(["en"])
            except NoTranscriptFound:
                # Last resort: grab whatever language is available
                transcript = next(iter(transcript_list))

        entries = transcript.fetch()
        return " ".join(entry["text"] for entry in entries).strip()

    except TranscriptsDisabled:
        return "[Transcripts are disabled for this video]"
    except Exception as e:
        return f"[Transcript unavailable: {str(e)}]"
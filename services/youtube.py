import os
import re
import isodate
from typing import Dict, Any, List
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound


YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")


def extract_video_id(url: str) -> str:
    patterns = [r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract YouTube video ID from URL: {url}")


def _parse_duration(iso_duration: str) -> int:
    try:
        return int(isodate.parse_duration(iso_duration).total_seconds())
    except Exception:
        return 0


def _extract_hashtags(text: str) -> List[str]:
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


def _safe_int(val) -> int:
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def fetch_youtube_metadata(url: str, video_id_label: str) -> Dict[str, Any]:
    vid = extract_video_id(url)
    print(f"[YouTube] Fetching metadata for video ID: {vid}")

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    video_resp = youtube.videos().list(
        part="snippet,statistics,contentDetails",
        id=vid
    ).execute()
    print(f"[YouTube] Video API response received")

    if not video_resp.get("items"):
        raise ValueError(f"YouTube video not found: {url}")

    item    = video_resp["items"][0]
    snippet = item["snippet"]
    stats   = item.get("statistics", {})
    content = item["contentDetails"]

    views    = _safe_int(stats.get("viewCount"))
    likes    = _safe_int(stats.get("likeCount"))
    comments = _safe_int(stats.get("commentCount"))

    engagement_rate = round((likes + comments) / views * 100, 4) if views > 0 else 0.0

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
        print(f"[YouTube] Channel subscribers: {followers}")

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

    meta = {
        "video_id":          video_id_label,
        "platform":          "youtube",
        "url":               url,
        "title":             title,
        "creator":           snippet.get("channelTitle") or "Unknown",
        "views":             views,
        "likes":             likes,
        "comments":          comments,
        "followers":         followers,
        "hashtags":          hashtags,
        "upload_date":       upload_date,
        "duration":          _parse_duration(content.get("duration", "PT0S")),
        "engagement_rate":   engagement_rate,
        "transcript_chunks": 0,
    }
    print(f"[YouTube] Metadata: views={views}, likes={likes}, comments={comments}, followers={followers}")
    return meta


def fetch_youtube_transcript(url: str) -> str:
    vid = extract_video_id(url)
    print(f"[YouTube] Fetching transcript for video ID: {vid}")

    try:
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list(vid)

        try:
            transcript = transcript_list.find_manually_created_transcript(["en"])
            print(f"[YouTube] Found manual English transcript")
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(["en"])
                print(f"[YouTube] Found auto-generated English transcript")
            except NoTranscriptFound:
                transcript = next(iter(transcript_list))
                print(f"[YouTube] Using first available transcript language")

        fetched = transcript.fetch()
        text = " ".join(
            entry.text if hasattr(entry, "text") else entry["text"]
            for entry in fetched
        ).strip()
        print(f"[YouTube] Transcript fetched ({len(text)} chars): {text[:200]}")
        return text

    except TranscriptsDisabled:
        print(f"[YouTube] Transcripts are disabled for {vid}")
        raise ValueError(f"Transcripts are disabled for video {vid}")
    except StopIteration:
        print(f"[YouTube] No transcripts available for {vid}")
        raise ValueError(f"No transcripts available for video {vid}")
    except Exception as e:
        print(f"[YouTube] Transcript error for {vid}: {e}")
        raise
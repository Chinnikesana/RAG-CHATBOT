"""
instagram.py
Handles all Instagram Reels processing via Supadata API.

Two separate API calls (both required):
  1. GET /v1/metadata  → views, likes, comments, author, duration, tags, date
  2. GET /v1/transcript → spoken transcript (native captions → AI fallback)

Supadata unified metadata schema (confirmed from official docs):
  response.platform          → "instagram"
  response.type              → "video"
  response.title             → null for Instagram (not available)
  response.description       → the Reel caption text
  response.author.username   → @handle
  response.author.displayName → display name
  response.stats.views       → int or null
  response.stats.likes       → int or null
  response.stats.comments    → int or null
  response.stats.shares      → int or null (usually null for Instagram)
  response.media.type        → "video"
  response.media.duration    → seconds as int
  response.media.thumbnailUrl→ thumbnail URL
  response.tags              → list of hashtag strings
  response.createdAt         → ISO 8601 string e.g. "2024-01-15T10:30:00Z"
  response.additionalData    → platform-specific extras (not guaranteed)

NOTE: Instagram does NOT expose follower count in any public API.
  response.author has no follower/subscriber field.
  We set followers=0 and surface "N/A" in the frontend.

Transcript response shape (text=true):
  response.content   → plain string
  response.lang      → ISO 639-1 language code
  response.availableLangs → list of available languages

Transcript response shape (text=false, default):
  response.content → list of { text, offset, duration, lang }

Free tier: 100 credits/month. 1 credit per metadata call, 1 credit per
native transcript, 2 credits/min for AI-generated transcript.

API docs: https://docs.supadata.ai/get-metadata
          https://docs.supadata.ai/get-transcript
"""

import os
import re
from typing import Dict, Any, List

import httpx

SUPADATA_API_KEY = os.getenv("SUPADATA_API_KEY", "")
SUPADATA_BASE    = "https://api.supadata.ai/v1"
TIMEOUT          = 90.0  # AI transcription can take up to 60s per docs


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _safe_int(val) -> int:
    """Safely convert any value to int. Handles None, strings, floats."""
    try:
        return int(val) if val is not None else 0
    except (ValueError, TypeError):
        return 0


def _extract_hashtags(text: str) -> List[str]:
    """Pull #hashtags out of caption/description text."""
    if not text:
        return []
    return list(dict.fromkeys(re.findall(r"#\w+", text)))


def _supadata_headers() -> Dict[str, str]:
    return {
        "x-api-key":    SUPADATA_API_KEY,
        "Content-Type": "application/json",
    }


# ─── Transcript ───────────────────────────────────────────────────────────────

def fetch_instagram_transcript(url: str) -> str:
    """
    GET /v1/transcript?url=<instagram_url>&text=true&mode=auto

    Response 200:
      { "content": "plain text string", "lang": "en", "availableLangs": [...] }

    Response 202 (large video, async):
      { "jobId": "uuid" }  → poll /v1/transcript/{jobId} every 1s
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.get(
            f"{SUPADATA_BASE}/transcript",
            headers=_supadata_headers(),
            params={
                "url":  url,
                "text": "true",   
                "mode": "auto",   
            },
        )

    if resp.status_code == 200:
        data    = resp.json()
        content = data.get("content", "")

        if isinstance(content, list):
            return " ".join(
                seg.get("text", "") for seg in content if seg.get("text")
            ).strip()

        return str(content).strip() if content else "[No spoken content found]"

    if resp.status_code == 202:
        job_id = resp.json().get("jobId", "")
        return _poll_transcript_job(job_id)

    if resp.status_code == 206:
        return "[Transcript unavailable for this Reel]"

    # Any other error
    return f"[Supadata transcript error {resp.status_code}: {resp.text[:200]}]"


def _poll_transcript_job(job_id: str) -> str:
    """Poll
    """
    import time

    if not job_id:
        return "[Transcript job ID missing]"

    with httpx.Client(timeout=30.0) as client:
        for _ in range(90):   # max 90s polling
            time.sleep(1)
            resp = client.get(
                f"{SUPADATA_BASE}/transcript/{job_id}",
                headers=_supadata_headers(),
            )
            if resp.status_code != 200:
                continue
            data   = resp.json()
            status = data.get("status", "")

            if status == "completed":
                content = data.get("content", "")
                if isinstance(content, list):
                    return " ".join(
                        seg.get("text", "") for seg in content if seg.get("text")
                    ).strip()
                return str(content).strip() if content else "[Empty transcript]"

            if status == "failed":
                return f"[Transcript generation failed: {data.get('error', 'unknown')}]"

    return "[Transcript job timed out after 90s]"


# Metadata 

def fetch_instagram_metadata(url: str, video_id_label: str) -> Dict[str, Any]:
    """
    GET /v1/metadata?url=<instagram_url>
    Response 200:
      {
        "platform": "instagram",
        "type": "video",
        "title": null, no title for inta reels
        "description": "",
        "author": {
          "username": "",
          "displayName": ""
        },
        "stats": {
          "views": int or null,
          "likes": int or null,
          "comments": int or null,
          "shares": int or null (usually null for Instagram)
        },
        "media": {
          "type": "video",
          "duration": seconds as int,
          "thumbnailUrl": string
        },
        "tags": ["#h1", "#h2"],
        "createdAt": ISO 8601 string e.g. "2024-01-15T10:30:00Z",
        "additionalData": {}  
      }
    """
    with httpx.Client(timeout=TIMEOUT) as client:
        resp = client.get(
            f"{SUPADATA_BASE}/metadata",
            headers=_supadata_headers(),
            params={"url": url},
        )

    if resp.status_code != 200:
        return f"[Supadata metadata error {resp.status_code}: {resp.text[:200]}]"

    data = resp.json()

    stats    = data.get("stats") or {}
    views    = _safe_int(stats.get("views"))
    likes    = _safe_int(stats.get("likes"))
    comments = _safe_int(stats.get("comments"))

    engagement_rate = (
        round((likes + comments) / views * 100, 4) if views > 0 else 0.0
    )

    author       = data.get("author") or {}
    display_name = author.get("displayName") or author.get("username") or "Unknown"

    title       = data.get("title") or ""
    description = data.get("description") or ""  # this is the Reel caption
    title       = title or description[:80] or "Instagram Reel"

   
    raw_tags = data.get("tags") or []
    tags_clean = [
        t if t.startswith("#") else f"#{t}"
        for t in raw_tags
    ]
    caption_tags = _extract_hashtags(description)
    hashtags = list(dict.fromkeys(tags_clean + caption_tags))[:20]

    media    = data.get("media") or {}
    duration = _safe_int(media.get("duration"))

    raw_date    = data.get("createdAt") or ""
    upload_date = raw_date[:10] if raw_date else "Unknown"

    return {
        "video_id":          video_id_label,
        "platform":          "instagram",
        "url":               url,
        "title":             title,
        "creator":           display_name,
        "views":             views,
        "likes":             likes,
        "comments":          comments,
        "followers":         0,        # Not available in public Instagram API
        "hashtags":          hashtags,
        "upload_date":       upload_date,
        "duration":          duration,
        "engagement_rate":   engagement_rate,
        "transcript_chunks": 0,        # filled after
    }


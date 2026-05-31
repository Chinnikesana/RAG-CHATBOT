"""
ingest.py
POST /api/ingest

Accepts 1 or 2 video URLs (YouTube or Instagram).
Auto-detects platform from URL and routes to the correct service.
Runs both videos concurrently with asyncio.gather.
"""

import asyncio
import uuid
from fastapi import APIRouter, HTTPException

from ..models.schemas import IngestRequest, IngestResponse, VideoMetadata
from ..services.youtube import fetch_youtube_metadata, fetch_youtube_transcript
from ..services.instagram import fetch_instagram_metadata, fetch_instagram_transcript
from ..services.vectorstore import chunk_and_store


router = APIRouter()


# ─── Platform Detection ───────────────────────────────────────────────────────

def detect_platform(url: str) -> str:
    """Returns 'youtube' or 'instagram' based on URL."""
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtube" in url_lower:
        return "youtube"
    if "instagram.com" in url_lower:
        return "instagram"
    raise ValueError(f"Unsupported platform URL: {url}")


# ─── Single Video Processor ───────────────────────────────────────────────────

async def process_video(url: str, video_id: str, session_id: str) -> VideoMetadata:
    """
    Detects platform, fetches metadata + transcript concurrently,
    chunks and stores transcript in ChromaDB.
    Returns a fully populated VideoMetadata object.
    """
    try:
        platform = detect_platform(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        if platform == "youtube":
            # Run metadata + transcript fetch concurrently (both are I/O bound)
            meta_dict, transcript = await asyncio.gather(
                asyncio.to_thread(fetch_youtube_metadata, url, video_id),
                asyncio.to_thread(fetch_youtube_transcript, url),
            )
        else:  # instagram
            meta_dict, transcript = await asyncio.gather(
                asyncio.to_thread(fetch_instagram_metadata, url, video_id),
                asyncio.to_thread(fetch_instagram_transcript, url),
            )

        # Chunk + embed + store in ChromaDB
        num_chunks = await asyncio.to_thread(
            chunk_and_store,
            text=transcript,
            session_id=session_id,
            video_id=video_id,
            platform=platform,
            creator=meta_dict["creator"],
        )

        meta_dict["transcript_chunks"] = num_chunks
        return VideoMetadata(**meta_dict)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process Video {video_id} ({url}): {str(e)}",
        )


# ─── Endpoint ─────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse)
async def ingest_videos(req: IngestRequest):
    """
    Ingests 1 or 2 video URLs.

    - Accepts any mix of YouTube and Instagram URLs.
    - Processes videos concurrently (parallel API calls).
    - Returns session_id + metadata for each video.
    """
    session_id = str(uuid.uuid4())

    tasks = [process_video(req.url_a, "A", session_id)]
    if req.url_b and req.url_b.strip():
        tasks.append(process_video(req.url_b, "B", session_id))

    results = await asyncio.gather(*tasks)

    return IngestResponse(
        session_id=session_id,
        video_a=results[0],
        video_b=results[1] if len(results) > 1 else None,
    )

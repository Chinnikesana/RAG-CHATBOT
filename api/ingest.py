import asyncio
import uuid
from fastapi import APIRouter, HTTPException

from models.schemas import IngestRequest, IngestResponse, VideoMetadata
from services.youtube import fetch_youtube_metadata, fetch_youtube_transcript
from services.instagram import fetch_instagram_metadata, fetch_instagram_transcript
from services.vectorstore import chunk_and_store


router = APIRouter()


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    if "instagram.com" in url_lower:
        return "instagram"
    raise ValueError(f"Unsupported platform URL: {url}")


async def process_video(url: str, video_id: str, session_id: str) -> VideoMetadata:
    platform = detect_platform(url)
    print(f"\n[Ingest] Processing Video {video_id} ({platform}) — {url}")

    print(f"[Ingest] Step 1: Fetching metadata for Video {video_id}")
    if platform == "youtube":
        meta_dict = await asyncio.to_thread(fetch_youtube_metadata, url, video_id)
    else:
        print("********insta***************")
        meta_dict = await asyncio.to_thread(fetch_instagram_metadata, url, video_id)
    print(f"[Ingest] Metadata fetched for Video {video_id}")

    print(f"[Ingest] Step 2: Fetching transcript for Video {video_id}")
    transcript = ""
    try:
        if platform == "youtube":
            transcript = await asyncio.to_thread(fetch_youtube_transcript, url)
        else:
            # Pass original URL so yt-dlp can pick the best audio format
            transcript = await asyncio.to_thread(fetch_instagram_transcript, url)
        print(f"[Ingest] Transcript fetched for Video {video_id} ({len(transcript)} chars)")
    except Exception as e:
        print(f"[Ingest] Transcript failed for Video {video_id}: {e}")
        transcript = ""

    print(f"[Ingest] Step 3: Chunking and embedding for Video {video_id}")
    num_chunks = await asyncio.to_thread(
        chunk_and_store,
        transcript=transcript,
        metadata=meta_dict,
        session_id=session_id,
        video_id=video_id,
        platform=platform,
        creator=meta_dict["creator"],
    )

    meta_dict["transcript_chunks"] = num_chunks
    print(f"[Ingest] Video {video_id} complete. Total chunks stored: {num_chunks}")
    return VideoMetadata(**meta_dict)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_videos(req: IngestRequest):
    session_id = str(uuid.uuid4())

    print(f"\n{'='*60}")
    print(f"[Ingest] New session: {session_id}")
    print(f"[Ingest] URL A: {req.url_a}")
    if req.url_b:
        print(f"[Ingest] URL B: {req.url_b}")
    print(f"{'='*60}")

    tasks = [process_video(req.url_a, "A", session_id)]
    if req.url_b and req.url_b.strip():
        tasks.append(process_video(req.url_b, "B", session_id))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            vid_label = "A" if i == 0 else "B"
            url = req.url_a if i == 0 else req.url_b
            print(f"[Ingest] ERROR processing Video {vid_label}: {result}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to process Video {vid_label} ({url}): {str(result)}",
            )

    print(f"\n[Ingest] All videos processed for session {session_id}")
    print(f"{'='*60}\n")

    return IngestResponse(
        session_id=session_id,
        video_a=results[0],
        video_b=results[1] if len(results) > 1 else None,
    )

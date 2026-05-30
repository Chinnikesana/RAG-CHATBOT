import uuid
import asyncio
from fastapi import APIRouter, HTTPException
from ..models.schemas import IngestRequest, IngestResponse, VideoMetadata
from ..services.transcript import extract_transcript
from ..services.metadata import fetch_video_metadata
from ..services.vectorstore import chunk_and_store

router = APIRouter()

async def process_video(url: str, video_id: str, session_id: str) -> VideoMetadata:
    """Extract metadata and transcript, then store in ChromaDB."""
    try:
        meta_dict = await asyncio.to_thread(fetch_video_metadata, url, video_id)
        transcript = await asyncio.to_thread(extract_transcript, url)
        
        # Chunk and embed
        num_chunks = await asyncio.to_thread(
            chunk_and_store,
            text=transcript,
            session_id=session_id,
            video_id=video_id,
            platform=meta_dict["platform"],
            creator=meta_dict["creator"]
        )
        
        meta_dict["transcript_chunks"] = num_chunks
        return VideoMetadata(**meta_dict)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed processing video {video_id} ({url}): {str(e)}")

@router.post("/ingest", response_model=IngestResponse)
async def ingest_videos(req: IngestRequest):
    """
    Ingests 1 or 2 URLs.
    Extracts metadata, downloads transcript, chunks, and stores in vector DB.
    """
    session_id = str(uuid.uuid4())
    
    tasks = [process_video(req.url_a, "A", session_id)]
    if req.url_b:
        tasks.append(process_video(req.url_b, "B", session_id))
        
    results = await asyncio.gather(*tasks)
    
    res = IngestResponse(
        session_id=session_id,
        video_a=results[0]
    )
    if len(results) > 1:
        res.video_b = results[1]
        
    return res

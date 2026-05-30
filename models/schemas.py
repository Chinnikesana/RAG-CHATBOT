from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Any


# ─── Ingest ───────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    url_a: str
    url_b: Optional[str] = None


class VideoMetadata(BaseModel):
    video_id: str          # "A" or "B"
    platform: str          # "youtube" | "instagram"
    url: str
    title: str
    creator: str
    views: int
    likes: int
    comments: int
    followers: int
    hashtags: List[str]
    upload_date: str
    duration: int          # seconds
    engagement_rate: float # (likes + comments) / views * 100
    transcript_chunks: int # how many chunks stored


class IngestResponse(BaseModel):
    session_id: str
    video_a: VideoMetadata
    video_b: Optional[VideoMetadata] = None


# ─── Chat ─────────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    question: str
    messages: List[Message] = []


class SourceChunk(BaseModel):
    video_id: str
    chunk_index: int
    text: str
    platform: str
    creator: str

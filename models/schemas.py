from pydantic import BaseModel
from typing import Optional, List, Dict, Any



class IngestRequest(BaseModel):
    url_a: str
    url_b: Optional[str] = None


class VideoMetadata(BaseModel):
    video_id: str           # "A" or "B"
    platform: str           # "youtube" | "insta"
    url: str
    title: str
    creator: str
    views: int
    likes: int
    comments: int
    followers: int
    hashtags: List[str]
    upload_date: str
    duration: int           # seconds
    engagement_rate: float  # (likes + comments) / views * 100
    transcript_chunks: int  # number of chunks stored in ChromaDB


class IngestResponse(BaseModel):
    session_id: str
    video_a: VideoMetadata
    video_b: Optional[VideoMetadata] = None



class Message(BaseModel):
    role: str     # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    question: str
    messages: List[Message] = []
    metadata: Optional[Dict[str, Any]] = None  # video metadata frontend

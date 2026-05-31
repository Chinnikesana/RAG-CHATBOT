"""
chat.py
POST /api/chat

Accepts question + full chat history + session_id.
Runs the pure RAG pipeline:
  1. Retrieve top-5 chunks from ChromaDB
  2. Build messages (system context + history + question)
  3. Stream Llama 3.1 tokens via Groq
  4. Append sources as final SSE event
"""

import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..models.schemas import ChatRequest
from ..services.rag_pipeline import retrieve, build_messages, stream_answer


router = APIRouter()


async def sse_generator(req: ChatRequest):
    """
    Server-Sent Events generator.

    Events:
      data: {"type": "token",   "content": "<text>"}
      data: {"type": "sources", "content": [{"video_id", "chunk_index", "platform", "creator"}]}
      data: {"type": "done"}
    """
    history = [{"role": m.role, "content": m.content} for m in req.messages]

    chunks = retrieve(req.session_id, req.question, top_k=5)

    metadata = getattr(req, "metadata", None) or {}

    messages = build_messages(
        question=req.question,
        chunks=chunks,
        metadata=metadata,
        history=history,
    )

    async for token in stream_answer(messages):
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    sources = [
        {
            "video_id":    c["video_id"],
            "chunk_index": c["chunk_index"],
            "platform":    c["platform"],
            "creator":     c["creator"],
        }
        for c in chunks
    ]
    yield f"data: {json.dumps({'type': 'sources', 'content': sources})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    RAG chat endpoint with SSE streaming.
    """
    return StreamingResponse(
        sse_generator(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   
        },
    )

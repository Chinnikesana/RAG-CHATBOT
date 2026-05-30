import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..models.schemas import ChatRequest
from ..services.rag_pipeline import retrieve, build_prompt, stream_llama

router = APIRouter()


async def chat_stream_generator(req: ChatRequest):
    """
    Simple RAG pipeline streamed via SSE:
      1. Retrieve relevant chunks from ChromaDB
      2. Build prompt with history + chunks
      3. Stream Llama response via Groq
    """
    history = [{"role": m.role, "content": m.content} for m in req.messages]

    
    chunks = retrieve(req.session_id, req.question)


    messages = build_prompt(
        question=req.question,
        chunks=chunks,
        metadata={}, 
        history=history,
    )

    async for token in stream_llama(messages):
        data = {"type": "token", "content": token}
        yield f"data: {json.dumps(data)}\n\n"

    sources_data = [
        {
            "video_id": c["video_id"],
            "chunk_index": c["chunk_index"],
            "platform": c["platform"],
            "creator": c["creator"],
        }
        for c in chunks
    ]
    yield f"data: {json.dumps({'type': 'sources', 'content': sources_data})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    RAG chat endpoint with Server-Sent Events (SSE) streaming.
    """
    return StreamingResponse(
        chat_stream_generator(req),
        media_type="text/event-stream",
    )

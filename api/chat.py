import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from models.schemas import ChatRequest
from services.rag_chain import retrieve, stream_answer


router = APIRouter()


async def sse_generator(req: ChatRequest):
    print(f"\n[Chat] Received question for session {req.session_id}: '{req.question}'")
    print(f"[Chat] History length: {len(req.messages)} messages")
    print(f"[Chat] Metadata keys: {list((req.metadata or {}).keys())}")

    history = [{"role": m.role, "content": m.content} for m in req.messages]

    chunks = retrieve(req.session_id, req.question, top_k=5)
    metadata = req.metadata or {}

    print(f"[Chat] Streaming response via LangChain Orchestrator...")

    token_count = 0
    async for token in stream_answer(req.question, chunks, metadata, history):
        token_count += 1
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

    print(f"[Chat] Streamed {token_count} tokens")

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
    print(f"[Chat] Done. Sources: {sources}\n")


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    return StreamingResponse(
        sse_generator(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

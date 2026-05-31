"""
rag_pipeline.py
Flow:
  question + history
    → embed question in ChromaDB similarity search
    → build prompt (system + metadata + chunks + history + question)
    → stream Llama 3.1 via Groq API
    → yield tokens
"""

import os
from typing import List, Dict, Any, AsyncGenerator

from groq import Groq

from .vectorstore import retrieve_chunks



GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

_groq_client: Groq | None = None


def _get_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client



SYSTEM_PROMPT = """You are an expert AI social media analyst helping creators understand their content performance.

Your job is to answer questions about the provided social media videos.

Rules:
1. Answer ONLY from the context provided (metadata + transcript excerpts).
2. When comparing videos, reference them as "Video A" or "Video B".
3. Always cite which video a transcript quote comes from.
4. If data is missing or unavailable, say so honestly. Never hallucinate.
5. For engagement rate questions, use the precomputed values from metadata.
6. For hook / content analysis, rely on the transcript excerpts."""



def build_messages(
    question: str,
    chunks: List[Dict[str, Any]],
    metadata: Dict[str, Any] | None = None,
    history: List[Dict[str, str]] | None = None,
) -> List[Dict[str, str]]:
    """
    Assembles the full message list for the Groq chat completion API.

    Structure:
      [system: SYSTEM_PROMPT + metadata context + transcript chunks]
      [assistant/user turns from history]
      [user: current question]
    """
    context_parts = []

    if metadata:
        context_parts.append("=== VIDEO METADATA ===")
        for v_id, data in metadata.items():
            if not data:
                continue
            context_parts.append(f"\nVideo {v_id.upper()} — {data['platform'].capitalize()}")
            context_parts.append(f"  Title:           {data['title']}")
            context_parts.append(f"  Creator:         {data['creator']}")
            context_parts.append(f"  Followers:       {data['followers']:,}")
            context_parts.append(f"  Views:           {data['views']:,}")
            context_parts.append(f"  Likes:           {data['likes']:,}")
            context_parts.append(f"  Comments:        {data['comments']:,}")
            context_parts.append(f"  Engagement Rate: {data['engagement_rate']}%")
            context_parts.append(f"  Duration:        {data['duration']}s")
            context_parts.append(f"  Uploaded:        {data['upload_date']}")
            if data.get("hashtags"):
                context_parts.append(f"  Hashtags:        {', '.join(data['hashtags'][:10])}")

    context_parts.append("\n=== RETRIEVED TRANSCRIPT EXCERPTS ===")
    if chunks:
        for idx, c in enumerate(chunks):
            context_parts.append(
                f"[Chunk {idx+1} | Video {c['video_id']} | {c['platform']} | Creator: {c['creator']}]\n"
                f"{c['text']}"
            )
    else:
        context_parts.append("No transcript excerpts retrieved.")

    context_block = "\n".join(context_parts)

    # ── Build messages list ──
    messages: List[Dict[str, str]] = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{context_block}"}
    ]

    if history:
        for msg in history:
            if msg.get("role") in ("user", "assistant") and msg.get("content"):
                messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": question})

    return messages



def retrieve(session_id: str, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Retrieve the most relevant transcript chunks from ChromaDB for this session."""
    return retrieve_chunks(session_id, question, top_k=top_k)



async def stream_answer(
    messages: List[Dict[str, str]],
) -> AsyncGenerator[str, None]:
    """
    Streams tokens from Groq's Llama 3.1 8B Instant model.
    The Groq SDK is synchronous; we iterate the stream and yield each token.
    """
    client = _get_client()

    stream = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        stream=True,
        temperature=0.4,
        max_tokens=1024,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            yield delta.content

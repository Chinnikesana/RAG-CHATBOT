
import os
from typing import List, Dict, Any, AsyncGenerator

from groq import Groq

from .vectorstore import retrieve_chunks


GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=GROQ_API_KEY)
    return _client



def retrieve(session_id: str, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Retrieve  most relevant transcript chunks"""
    return retrieve_chunks(session_id, question, top_k=top_k)



SYSTEM_PROMPT = """You are an expert AI social media analyst. Your job is to answer questions about social media videos.
INSTRUCTIONS:
1. Answer the user's question accurately using ONLY the context provided.
2. Compare metrics when asked.
3. If citing transcript quotes, mention the video (e.g. "Video A").
4. If you do not know the answer based on the context, say so. Do not hallucinate."""


def build_prompt(
    question: str,
    chunks: List[Dict[str, Any]],
    metadata: Dict[str, Any] | None = None,
    history: List[Dict[str, str]] | None = None,
) -> List[Dict[str, str]]:
    """
    Build the messages list for the chat completion.
  
    """
  
    context_parts = []

    if metadata:
        context_parts.append("=== VIDEO METADATA ===")
        for v_id, data in metadata.items():
            if data:
                context_parts.append(f"Video {v_id.upper()} ({data['platform']}):")
                context_parts.append(f"- Creator: {data['creator']} (Followers: {data['followers']})")
                context_parts.append(f"- Views: {data['views']}, Likes: {data['likes']}, Comments: {data['comments']}")
                context_parts.append(f"- Engagement Rate: {data['engagement_rate']}%")
                context_parts.append(f"- Uploaded: {data['upload_date']}, Duration: {data['duration']}s")
                context_parts.append(f"- Hashtags: {', '.join(data['hashtags'])}")
                context_parts.append("")

    context_parts.append("=== RETRIEVED TRANSCRIPT EXCERPTS ===")
    if not chunks:
        context_parts.append("No transcript chunks available.")
    else:
        for idx, c in enumerate(chunks):
            context_parts.append(
                f"[Source {idx+1}] Video {c['video_id']} (Creator: {c['creator']}): {c['text']}"
            )

    context_block = "\n".join(context_parts)

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{context_block}"}
    ]

    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

    # Current question
    messages.append({"role": "user", "content": question})

    return messages



async def stream_llama(messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """
    Stream tokens from Groq's Llama 3.1 8B Instant.
    Yields each token string as it arrives.
    """
    client = _get_client()

    stream = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        stream=True,
        temperature=0.7,
        max_tokens=1024,
    )

    for chunk in stream:
        token = chunk.choices[0].delta.content
        if token:
            yield token

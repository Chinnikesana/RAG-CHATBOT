import os
from typing import List, Dict, Any, AsyncGenerator

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from services.vectorstore import retrieve_chunks

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

_llm: ChatGroq | None = None


def get_llm() -> ChatGroq:
    global _llm
    if _llm is not None:
        return _llm
    kwargs: Dict[str, Any] = dict(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0.4,
        streaming=True,
    )
    # max_tokens renamed to max_completion_tokens in langchain-groq >= 0.2
    try:
        import langchain_groq as lg
        ver = tuple(int(x) for x in getattr(lg, "__version__", "0.1.0").split(".")[:2])
        if ver >= (0, 2):
            kwargs["max_completion_tokens"] = 1024
        else:
            kwargs["max_tokens"] = 1024
    except Exception:
        pass
    _llm = ChatGroq(**kwargs)
    return _llm


def retrieve(session_id: str, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    print(f"[RAG] Retrieving top {top_k} chunks for session {session_id}, query: '{question}'")
    chunks = retrieve_chunks(session_id, question, top_k=top_k)
    print(f"[RAG] Retrieved {len(chunks)} chunks.")
    return chunks


SYSTEM_PROMPT = """\
You are an expert AI social media analyst helping creators understand their content performance.

Rules:
1. Answer ONLY from the context provided (metadata + transcript excerpts).
2. When comparing videos, reference them as "Video A" or "Video B".
3. Always cite which video a transcript quote comes from.
4. If data is missing or unavailable, say so honestly. Never hallucinate.
5. For engagement stats, use the metadata section of the context.
6. For hook / content analysis, rely on the transcript excerpts.
"""


def _build_context(chunks: List[Dict[str, Any]], metadata: Dict[str, Any]) -> str:
    parts = []

    # ── Metadata section ──────────────────────────────────────────────────────
    if metadata:
        parts.append("=== VIDEO METADATA ===")
        for vid_key, data in metadata.items():
            if not data:
                continue
            vid_label = vid_key.upper()
            platform  = data.get("platform", "unknown").capitalize()
            followers = data.get("followers", 0)
            followers_str = (
                "N/A (no public API)"
                if data.get("platform") == "instagram" and followers == 0
                else f"{followers:,}"
            )
            parts += [
                f"\nVideo {vid_label} — {platform}",
                f"  Title:           {data.get('title', 'N/A')}",
                f"  Creator:         {data.get('creator', 'Unknown')}",
                f"  Followers:       {followers_str}",
                f"  Views:           {data.get('views', 0):,}",
                f"  Likes:           {data.get('likes', 0):,}",
                f"  Comments:        {data.get('comments', 0):,}",
                f"  Engagement Rate: {data.get('engagement_rate', 0)}%",
                f"  Duration:        {data.get('duration', 0)}s",
                f"  Uploaded:        {data.get('upload_date', 'Unknown')}",
            ]
            if data.get("hashtags"):
                parts.append(f"  Hashtags:        {', '.join(data['hashtags'][:10])}")

    # ── Transcript chunks ─────────────────────────────────────────────────────
    parts.append("\n=== RETRIEVED TRANSCRIPT EXCERPTS ===")
    if chunks:
        for idx, c in enumerate(chunks):
            chunk_label = c.get("chunk_type", "transcript").upper()
            parts.append(
                f"[Chunk {idx+1} | {chunk_label} | Video {c['video_id']} "
                f"| {c['platform']} | Creator: {c['creator']}]\n{c['text']}"
            )
    else:
        parts.append("No transcript retrieved.")

    return "\n".join(parts)


async def stream_answer(
    question: str,
    chunks: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    history: List[Dict[str, str]],
) -> AsyncGenerator[str, None]:
    """
    Streams tokens directly from ChatGroq — no AgentExecutor needed.
    Works with langchain-groq 0.1.x through 1.x.
    """
    context = _build_context(chunks, metadata)

    # Build message list
    messages = [SystemMessage(content=f"{SYSTEM_PROMPT}\n\n{context}")]

    for msg in history:
        role    = msg.get("role", "")
        content = msg.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=question))

    llm = get_llm()
    print(f"[RAG] Streaming answer via ChatGroq ({GROQ_MODEL})...")

    async for chunk in llm.astream(messages):
        if chunk.content:
            yield chunk.content

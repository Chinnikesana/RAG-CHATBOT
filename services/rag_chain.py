import os
from typing import List, Dict, Any, AsyncGenerator
import json

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage
from langchain.agents import AgentExecutor, create_tool_calling_agent

from services.vectorstore import retrieve_chunks

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

_metadata_store: Dict[str, Any] = {}

def update_metadata_store(metadata: Dict[str, Any]):
    global _metadata_store
    _metadata_store = metadata

from langchain_core.tools import StructuredTool

def _get_video_stats_func(video_id: str) -> str:
    clean_id = video_id.lower().replace("video", "").strip()
    data = _metadata_store.get(clean_id)
    if not data:
        return f"No metadata found for Video {video_id}."
    
    return (
        f"Stats for Video {video_id.upper()}:\n"
        f"Views: {data.get('views', 0):,}\n"
        f"Likes: {data.get('likes', 0):,}\n"
        f"Comments: {data.get('comments', 0):,}\n"
        f"Engagement Rate: {data.get('engagement_rate', 0)}%"
    )

get_video_stats = StructuredTool.from_function(
    func=_get_video_stats_func,
    name="get_video_stats",
    description="Returns engagement rate, views, likes, and comments for Video A or B. Use this to lookup stats."
)

def get_llm():
    return ChatGroq(
        api_key=GROQ_API_KEY,
        model=GROQ_MODEL,
        temperature=0.4,
        max_tokens=1024
    )

def retrieve(session_id: str, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    print(f"[RAG] Retrieving top {top_k} chunks for session {session_id}, query: '{question}'")
    chunks = retrieve_chunks(session_id, question, top_k=top_k)
    print(f"[RAG] Retrieved {len(chunks)} chunks.")
    return chunks

async def stream_answer(
    question: str,
    chunks: List[Dict[str, Any]],
    metadata: Dict[str, Any],
    history: List[Dict[str, str]]
) -> AsyncGenerator[str, None]:
    
    update_metadata_store(metadata)
    
    context_parts = ["=== RETRIEVED TRANSCRIPT EXCERPTS ==="]
    if chunks:
        for idx, c in enumerate(chunks):
            chunk_label = c.get("chunk_type", "transcript").upper()
            context_parts.append(
                f"[Chunk {idx+1} | {chunk_label} | Video {c['video_id']} | {c['platform']} | Creator: {c['creator']}]\n"
                f"{c['text']}"
            )
    else:
        context_parts.append("No transcript retrieved.")
    context_block = "\n".join(context_parts)

    chat_history = []
    for msg in history:
        if msg["role"] == "user":
            chat_history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            chat_history.append(AIMessage(content=msg["content"]))

    system_msg = """You are an expert AI social media analyst helping creators understand their content performance.
Your job is to answer questions about the provided social media videos.

Rules:
1. Answer ONLY from the context provided (metadata + transcript excerpts).
2. When comparing videos, reference them as "Video A" or "Video B".
3. Always cite which video a transcript quote comes from.
4. If data is missing or unavailable, say so honestly. Never hallucinate.
5. For hook / content analysis, rely on the transcript excerpts.
6. For engagement stats, use your tool to look them up.

Context:
{context}"""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    tools = [get_video_stats]
    llm = get_llm()
    
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools)

    print("[RAG] Calling LangChain AgentExecutor (streaming)...")
    
    async for event in agent_executor.astream_events(
        {
            "question": question, 
            "chat_history": chat_history,
            "context": context_block
        },
        version="v1"
    ):
        kind = event["event"]
        if kind == "on_chat_model_stream":
            chunk = event["data"]["chunk"]
            if chunk.content:
                yield chunk.content
        elif kind == "on_tool_start":
            print(f"[RAG] LangChain Orchestrator called tool: {event['name']}")

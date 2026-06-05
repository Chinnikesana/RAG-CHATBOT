import os
from typing import List, Dict, Any

import chromadb
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

_embeddings: HuggingFaceEmbeddings | None = None
_collection: chromadb.Collection | None = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-m3",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings


def _get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        _collection = client.get_or_create_collection(
            name="rag_transcripts",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    separators=["\n\n", "\n", ".", " ", ""],
)


def _build_metadata_text(metadata: Dict[str, Any]) -> str:
    platform = metadata.get("platform", "")
    followers = metadata.get("followers", 0)
    # Show honest message when followers aren't available
    followers_str = (
        "N/A (no cookies configured)"
        if platform == "instagram" and followers == 0
        else f"{followers:,}"
    )
    lines = [
        f"Video {metadata['video_id']} ({metadata['platform'].capitalize()})",
        f"Title: {metadata.get('title', 'N/A')}",
        f"Creator: {metadata.get('creator', 'Unknown')}",
        f"Followers: {followers_str}",
        f"Views: {metadata.get('views', 0):,}",
        f"Likes: {metadata.get('likes', 0):,}",
        f"Comments: {metadata.get('comments', 0):,}",
        f"Engagement Rate: {metadata.get('engagement_rate', 0)}%",
        f"Duration: {metadata.get('duration', 0)} seconds",
        f"Upload Date: {metadata.get('upload_date', 'Unknown')}",
    ]
    if metadata.get("hashtags"):
        lines.append(f"Hashtags: {', '.join(metadata['hashtags'][:15])}")
    return "\n".join(lines)


def chunk_and_store(
    transcript: str,
    metadata: Dict[str, Any],
    session_id: str,
    video_id: str,
    platform: str,
    creator: str,
) -> int:
    meta_text = _build_metadata_text(metadata)
    print(f"[VectorStore] Metadata chunk for Video {video_id}:\n{meta_text}")

    all_chunks = [meta_text]

    if transcript and transcript.strip():
        transcript_chunks = _splitter.split_text(transcript)
        print(f"[VectorStore] Transcript split into {len(transcript_chunks)} chunks for Video {video_id}")
        all_chunks.extend(transcript_chunks)
    else:
        print(f"[VectorStore] No transcript to chunk for Video {video_id}")

    emb_model = _get_embeddings()
    collection = _get_collection()

    documents = []
    metadatas = []
    ids = []

    for i, chunk in enumerate(all_chunks):
        documents.append(chunk)
        metadatas.append({
            "session_id":  session_id,
            "video_id":    video_id,
            "chunk_index": i,
            "chunk_type":  "metadata" if i == 0 else "transcript",
            "platform":    platform,
            "creator":     creator,
        })
        ids.append(f"{session_id}_{video_id}_{i}")

    print(f"[VectorStore] Embedding {len(documents)} chunks for Video {video_id}...")
    embeddings_list = emb_model.embed_documents(documents)

    collection.upsert(
        documents=documents,
        embeddings=embeddings_list,
        metadatas=metadatas,
        ids=ids,
    )

    print(f"[VectorStore] Stored {len(documents)} chunks for Video {video_id}")
    return len(documents)


def retrieve_chunks(
    session_id: str,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    emb_model  = _get_embeddings()
    collection = _get_collection()

    query_embedding = emb_model.embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"session_id": session_id},
    )

    docs  = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    return [
        {
            "text":        doc,
            "video_id":    meta["video_id"],
            "chunk_index": meta["chunk_index"],
            "chunk_type":  meta.get("chunk_type", "transcript"),
            "platform":    meta["platform"],
            "creator":     meta["creator"],
        }
        for doc, meta in zip(docs, metas)
    ]

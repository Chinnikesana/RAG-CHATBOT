"""
vectorstore.py
ChromaDB persistent vector store with BGE-M3 embeddings.
Uses LangChain only for:
  - RecursiveCharacterTextSplitter  (chunking)
  - HuggingFaceBgeEmbeddings        (BGE-M3 embedding model)
All DB interactions are direct chromadb client calls for full control.
"""

import os
from typing import List, Dict, Any

import chromadb
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter



CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
HF_HOME = os.getenv("HF_HOME", "./hf_cache")

CHUNK_SIZE    = 600
CHUNK_OVERLAP = 100



_embeddings: HuggingFaceBgeEmbeddings | None = None
_collection: chromadb.Collection | None = None


def _get_embeddings() -> HuggingFaceBgeEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceBgeEmbeddings(
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


#  Public API 
def chunk_and_store(
    text: str,
    session_id: str,
    video_id: str,
    platform: str,
    creator: str,
) -> int:
    """
    Splits transcript into chunks, embeds with BGE-M3, stores in ChromaDB.
    Each chunk is tagged with session_id so retrieval is session-isolated.
    Returns the number of chunks stored.
    """
    if not text or text.startswith("["):
        return 0

    chunks = _splitter.split_text(text)
    if not chunks:
        return 0

    emb_model = _get_embeddings()
    collection = _get_collection()

    documents  = []
    metadatas  = []
    ids        = []

    for i, chunk in enumerate(chunks):
        documents.append(chunk)
        metadatas.append({
            "session_id":  session_id,
            "video_id":    video_id,
            "chunk_index": i,
            "platform":    platform,
            "creator":     creator,
        })
        ids.append(f"{session_id}_{video_id}_{i}")

    # embed_documents returns List[List[float]]
    embeddings_list = emb_model.embed_documents(documents)

    collection.upsert(
        documents=documents,
        embeddings=embeddings_list,
        metadatas=metadatas,
        ids=ids,
    )

    return len(chunks)


def retrieve_chunks(
    session_id: str,
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Embeds the query and retrieves the top_k most relevant chunks
    for the given session from ChromaDB.
    """
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
            "platform":    meta["platform"],
            "creator":     meta["creator"],
        }
        for doc, meta in zip(docs, metas)
    ]

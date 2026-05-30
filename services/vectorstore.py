import os
from typing import List, Dict, Any

# ChromaDB for local persistent vector store
import chromadb
from chromadb.config import Settings

# BGE-M3 for high quality multilingual embeddings, runs locally via sentence-transformers
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")

# Initialize Embedding Model once globally
# BGE-M3 is highly rated on MTEB, fits locally, and is very fast on CPU
model_name = "BAAI/bge-m3"
model_kwargs = {"device": "cpu"}
encode_kwargs = {"normalize_embeddings": True}

embeddings = HuggingFaceBgeEmbeddings(
    model_name=model_name,
    model_kwargs=model_kwargs,
    encode_kwargs=encode_kwargs
)

# Initialize ChromaDB client
chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

# We use a single collection and isolate sessions via metadata filtering
collection = chroma_client.get_or_create_collection(
    name="rag_transcripts",
    metadata={"hnsw:space": "cosine"}
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=100,
    separators=["\n\n", "\n", ".", " ", ""]
)


def chunk_and_store(
    text: str,
    session_id: str,
    video_id: str,
    platform: str,
    creator: str
) -> int:
    """
    Chunks transcript, embeds, and stores in ChromaDB.
    Returns the number of chunks stored.
    """
    if not text or text.startswith("[Transcript unavailable"):
        return 0

    chunks = text_splitter.split_text(text)
    if not chunks:
        return 0

    documents = []
    metadatas = []
    ids = []

    for i, chunk in enumerate(chunks):
        documents.append(chunk)
        metadatas.append({
            "session_id": session_id,
            "video_id": video_id,
            "chunk_index": i,
            "platform": platform,
            "creator": creator
        })
        ids.append(f"{session_id}_{video_id}_{i}")

    # Langchain HuggingFace embeddings wraps sentence_transformers,
    # but we interact directly with chroma for full control over metadata filtering.
    
    # We must generate embeddings directly for the Chroma client
    # HuggingFaceBgeEmbeddings has an `embed_documents` method
    embedded_docs = embeddings.embed_documents(documents)

    # Upsert into Chroma (batch insert)
    collection.upsert(
        documents=documents,
        embeddings=embedded_docs,
        metadatas=metadatas,
        ids=ids
    )

    return len(chunks)


def retrieve_chunks(session_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieves the most relevant chunks for a specific session.
    """
    query_embedding = embeddings.embed_query(query)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"session_id": session_id}
    )

    if not results["documents"] or not results["documents"][0]:
        return []

    # Flatten results (we only sent 1 query)
    docs = results["documents"][0]
    metas = results["metadatas"][0]

    out = []
    for doc, meta in zip(docs, metas):
        out.append({
            "text": doc,
            "video_id": meta["video_id"],
            "chunk_index": meta["chunk_index"],
            "platform": meta["platform"],
            "creator": meta["creator"]
        })
    return out

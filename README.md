# RAG Chatbot Backend

## Setup

1. Setup Python venv
python -m venv venv
venv\Scripts\activate


2. Install dependencies

pip install -r requirements.tx

3. Run the server

python main.py
# Server runs at http://localhost:8000


About Application:
frontend - used React js and tailwind css.
backend - FAST API
vector db- chromadb
embeddings - BAAI/bge-m3
transcript- Transcript: youtube-transcript-api / yt-dlp + groq  Whisper
LLM - grok llama 3.1 (fastest)

flow :
1. input 2 urls(you tube+ Instagram Reel) 
2.The backend processes both videos simultaneously to save time:
    a.  tube - used  YouTube Data API v3 for metadata +  youtube-transcript-ap  for transcription.
    b. instagram - instagrapi for metadata   + yt-dlp to download the native audio stream and pass it directly to Groq Whisper for fast transcription .
3.  The backend takes all collected data (metadata + transcripts), chunks it using LangChain's RecursiveCharacterTextSplitter, converts it into embeddings using the **bge-m3** model, and stores the vectors in ChromaDB.
4. frontend ui will display chatting ui on sucessfull processing of vedios.
5. When the user asks a question, the frontend sends the current question + the complete chat history to the `/chat` endpoint.
6 RAG Orchestration (LangChain):
   * The backend converts the current question into an embedding and performs a similarity search in ChromaDB to fetch the top 5 most relevant chunks.
   * LangChain acts as the orchestrator. It uses a `ChatPromptTemplate` to assemble the context, injects the chat history via `MessagesPlaceholder`, and binds a custom `@tool` so the agent can look up exact video stats when needed.
   * The Groq LLM generates the final answer based on the retrieved chunks, history, and user query.
7. Streaming: The answer is streamed back to the frontend in real-time using Server-Sent Events (SSE) for a fast, ChatGPT-like experience.
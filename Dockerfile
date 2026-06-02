FROM python:3.11-slim

# Install system dependencies
# yt-dlp needs ffmpeg for audio extraction
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt


# Copy application code
COPY . .

# Create directories that the app writes to at runtime
RUN mkdir -p chroma_db hf_cache

# HuggingFace cache — BGE-M3 downloads here on first run
ENV HF_HOME=/app/hf_cache
ENV TRANSFORMERS_CACHE=/app/hf_cache

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
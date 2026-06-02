import { VideoMeta } from '../components/VideoCard';

export const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

export interface IngestResponse {
  session_id: string;
  video_a: VideoMeta;
  video_b?: VideoMeta;
}

export const api = {
  async ingestVideos(urlA: string, urlB?: string): Promise<IngestResponse> {
    const body: Record<string, string> = { url_a: urlA };
    if (urlB && urlB.trim()) body.url_b = urlB;

    const res = await fetch(`${API_BASE}/api/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      let errorMessage = `Server error: ${res.status}`;
      try {
        const errorData = await res.json();
        if (errorData.detail) errorMessage = errorData.detail;
      } catch {
        // ignore
      }
      throw new Error(errorMessage);
    }

    return res.json();
  }
};

import { useState } from 'react';
import { Youtube, Instagram, Zap } from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface IngestFormProps {
  onSuccess: () => void;
  isIngesting: boolean;
  setIsIngesting: (v: boolean) => void;
}

export default function IngestForm({ onSuccess, isIngesting, setIsIngesting }: IngestFormProps) {
  const [youtubeUrl, setYoutubeUrl] = useState('');
  const [instagramUrl, setInstagramUrl] = useState('');
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!youtubeUrl.trim() || !instagramUrl.trim()) {
      setError('Both URLs are required.');
      return;
    }
    setError('');
    setIsIngesting(true);
    try {
      const res = await fetch(`${API_BASE}/api/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ youtube_url: youtubeUrl, instagram_url: instagramUrl }),
      });
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ingestion failed.');
      setIsIngesting(false);
    }
  }

  return (
    <div className="rounded-xl border border-white/[0.07] bg-[#1a1a1a] p-5">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-7 h-7 rounded-lg bg-blue-500/15 flex items-center justify-center">
          <Zap size={14} className="text-blue-400" />
        </div>
        <span className="text-sm font-semibold text-white tracking-wide">Analyze Videos</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="relative group">
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-red-400/70 pointer-events-none">
            <Youtube size={15} />
          </div>
          <input
            type="url"
            placeholder="YouTube URL"
            value={youtubeUrl}
            onChange={e => setYoutubeUrl(e.target.value)}
            disabled={isIngesting}
            className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-[#111] border border-white/[0.08] text-sm text-white placeholder-white/25
              focus:outline-none focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/20 transition-all
              disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        <div className="relative group">
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-pink-400/70 pointer-events-none">
            <Instagram size={15} />
          </div>
          <input
            type="url"
            placeholder="Instagram Reel URL"
            value={instagramUrl}
            onChange={e => setInstagramUrl(e.target.value)}
            disabled={isIngesting}
            className="w-full pl-9 pr-4 py-2.5 rounded-lg bg-[#111] border border-white/[0.08] text-sm text-white placeholder-white/25
              focus:outline-none focus:border-blue-500/60 focus:ring-1 focus:ring-blue-500/20 transition-all
              disabled:opacity-50 disabled:cursor-not-allowed"
          />
        </div>

        {error && (
          <p className="text-xs text-red-400/80 px-1">{error}</p>
        )}

        <button
          type="submit"
          disabled={isIngesting}
          className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white text-sm font-medium
            transition-colors disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {isIngesting ? (
            <>
              <div className="spinner" />
              <span>Ingesting…</span>
            </>
          ) : (
            <span>Analyze Videos</span>
          )}
        </button>
      </form>
    </div>
  );
}

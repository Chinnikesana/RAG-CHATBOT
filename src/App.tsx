import { useState } from 'react';
import { Video, Sparkles, ArrowRight, Zap } from 'lucide-react';
import VideoCard, { VideoMeta } from './components/VideoCard';
import ChatPanel from './components/ChatPanel';
import { api } from './lib/api';

type AppStep = 'input' | 'processing' | 'chat';

export default function App() {
  const [sessionId, setSessionId] = useState<string>('');
  const [step, setStep] = useState<AppStep>('input');
  const [videos, setVideos] = useState<VideoMeta[]>([]);
  const [urlA, setUrlA] = useState('');
  const [urlB, setUrlB] = useState('');
  const [error, setError] = useState('');
  const [metadata, setMetadata] = useState<Record<string, any>>({});

  async function handleProcess() {
    if (!urlA.trim()) {
      setError('At least Video A URL is required.');
      return;
    }
    setError('');
    setStep('processing');

    try {
      const data = await api.ingestVideos(urlA, urlB || undefined);

      setSessionId(data.session_id);

      const newVideos: VideoMeta[] = [data.video_a];
      const meta: Record<string, any> = { a: data.video_a };

      if (data.video_b) {
        newVideos.push(data.video_b);
        meta.b = data.video_b;
      }

      setVideos(newVideos);
      setMetadata(meta);
      setStep('chat');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Processing failed.');
      setStep('input');
    }
  }

  return (
    <div className="flex flex-col h-screen">
      <header className="flex-shrink-0 flex items-center justify-between px-6 py-4 bg-white/60 backdrop-blur-sm border-b border-violet-200/50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-400/30">
            <Video size={16} className="text-white" />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-base font-bold bg-gradient-to-r from-violet-700 to-purple-600 bg-clip-text text-transparent">RAG Video Compare</span>
            <span className="text-[10px] font-semibold text-violet-400 bg-violet-100 px-2 py-0.5 rounded-full uppercase tracking-wide">Beta</span>
          </div>
        </div>
        {sessionId && (
          <div className="flex items-center gap-2 text-xs font-medium text-violet-400">
            <span className="font-mono bg-violet-100 px-2 py-1 rounded border border-violet-200/60 text-violet-600">
              {sessionId.slice(0, 8)}
            </span>
          </div>
        )}
      </header>

      <main className="flex-1 overflow-hidden">
        {step === 'input' && (
          <div className="h-full flex items-center justify-center p-8">
            <div className="w-full max-w-xl">
              <div className="text-center mb-8">
                <div className="inline-flex items-center gap-2 bg-gradient-to-r from-violet-100 to-purple-50 border border-violet-200/60 rounded-full px-4 py-1.5 mb-4">
                  <Sparkles size={14} className="text-violet-500" />
                  <span className="text-xs font-semibold text-violet-600">AI-Powered Video Analysis</span>
                </div>
                <h1 className="text-3xl font-bold text-violet-950 mb-3">Compare Video Content</h1>
                <p className="text-violet-600/80 text-sm max-w-md mx-auto">
                  Enter YouTube or Instagram Reel URLs to analyze and compare their content using RAG-powered chat.
                </p>
              </div>

              <div className="bg-white/80 backdrop-blur-sm rounded-2xl border border-violet-200/60 p-6 shadow-xl shadow-violet-900/10">
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-violet-700 mb-1.5 uppercase tracking-wide">
                      Video A URL
                    </label>
                    <input
                      type="url"
                      placeholder="https://youtube.com/watch?v=... or https://instagram.com/reel/..."
                      value={urlA}
                      onChange={e => setUrlA(e.target.value)}
                      className="w-full px-4 py-3.5 rounded-xl bg-violet-50/50 border border-violet-200 text-violet-900 text-sm placeholder:text-violet-300 focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-transparent transition-all"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-violet-700 mb-1.5 uppercase tracking-wide">
                      Video B URL
                      <span className="text-violet-400 font-normal ml-1">(optional)</span>
                    </label>
                    <input
                      type="url"
                      placeholder="https://youtube.com/watch?v=... or https://instagram.com/reel/..."
                      value={urlB}
                      onChange={e => setUrlB(e.target.value)}
                      className="w-full px-4 py-3.5 rounded-xl bg-violet-50/50 border border-violet-200 text-violet-900 text-sm placeholder:text-violet-300 focus:outline-none focus:ring-2 focus:ring-violet-400 focus:border-transparent transition-all"
                    />
                  </div>

                  {error && (
                    <p className="text-xs text-red-500 font-medium">{error}</p>
                  )}

                  <button
                    onClick={handleProcess}
                    className="w-full py-3.5 rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white text-sm font-semibold shadow-lg shadow-violet-400/25 transition-all flex items-center justify-center gap-2 group"
                  >
                    <span>Process Videos</span>
                    <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
                  </button>
                </div>

                <p className="text-center text-xs text-violet-400/70 mt-4">
                  Supports YouTube and Instagram Reels
                </p>
              </div>
            </div>
          </div>
        )}

        {step === 'processing' && (
          <div className="h-full flex items-center justify-center p-8">
            <div className="text-center">
              <div className="relative w-24 h-24 mx-auto mb-6">
                <div className="absolute inset-0 rounded-full bg-gradient-to-r from-violet-400 to-purple-400 opacity-20 animate-pulse" />
                <div className="absolute inset-2 rounded-full bg-gradient-to-r from-violet-500 to-purple-500 opacity-30 animate-pulse" style={{ animationDelay: '0.15s' }} />
                <div className="absolute inset-0 flex items-center justify-center animate-pulse">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/40">
                    <Zap size={20} className="text-white" />
                  </div>
                </div>
              </div>

              <h2 className="text-xl font-bold text-violet-900 mb-2">Processing Videos</h2>
              <p className="text-violet-500/80 text-sm max-w-sm mx-auto mb-4">
                Analyzing video content and building knowledge base…
              </p>

              <div className="flex items-center justify-center gap-3 text-violet-400">
                <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                <div className="w-2 h-2 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}

        {step === 'chat' && (
          <div className="flex flex-1 overflow-hidden gap-0 h-full">
            <aside className="w-[38%] min-w-[380px] max-w-[450px] flex-shrink-0 overflow-y-auto border-r border-violet-200/50 bg-white/40 backdrop-blur-sm p-5 space-y-4">
              {videos[0] && <VideoCard video={videos[0]} label="Video A" />}
              {videos[1] && <VideoCard video={videos[1]} label="Video B" />}
            </aside>

            <div className="flex-1 min-w-0 p-5 bg-gradient-to-br from-violet-50/50 to-white/30">
              <ChatPanel sessionId={sessionId} isReady={true} metadata={metadata} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

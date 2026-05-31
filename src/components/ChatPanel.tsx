import { useState, useRef, useEffect } from 'react';
import { Send, Bot, MessageCircle, Sparkles } from 'lucide-react';
import MessageBubble, { Message } from './MessageBubble';
import { API_BASE } from '../lib/api';

interface ChatPanelProps {
  sessionId: string;
  isReady: boolean;
  metadata?: Record<string, any>;
}

export default function ChatPanel({ sessionId, isReady, metadata }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isSending, setIsSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  async function sendMessage() {
    const question = input.trim();
    if (!question || isSending || !isReady) return;

    setInput('');
    setIsSending(true);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question,
    };

    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      sources: [],
      isStreaming: true,
    };

    setMessages(prev => [...prev, userMsg, assistantMsg]);

    const history = messages
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({ role: m.role, content: m.content }));

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          question,
          messages: history,
          metadata: metadata || {},
        }),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const payload = line.slice(6).trim();
          if (!payload || payload === '[DONE]') continue;

          try {
            const parsed = JSON.parse(payload);

            if (parsed.type === 'token' && parsed.content) {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId
                    ? { ...m, content: m.content + parsed.content }
                    : m
                )
              );
            }

            if (parsed.type === 'sources' && parsed.content) {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId ? { ...m, sources: parsed.content } : m
                )
              );
            }

            if (parsed.type === 'done') {
              setMessages(prev =>
                prev.map(m =>
                  m.id === assistantId ? { ...m, isStreaming: false } : m
                )
              );
            }
          } catch {
            // skip unparseable lines
          }
        }
      }
    } catch (err) {
      const errText = err instanceof Error ? err.message : 'Something went wrong.';
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: errText, isStreaming: false }
            : m
        )
      );
    } finally {
      setMessages(prev =>
        prev.map(m => (m.id === assistantId ? { ...m, isStreaming: false } : m))
      );
      setIsSending(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  return (
    <div className="flex flex-col h-full bg-white/80 backdrop-blur-sm rounded-2xl border border-violet-200/60 shadow-xl shadow-violet-900/5 overflow-hidden">
      <div className="px-5 py-4 border-b border-violet-100 flex items-center justify-between flex-shrink-0 bg-gradient-to-r from-violet-50 to-purple-50">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-purple-500 flex items-center justify-center shadow-lg shadow-violet-400/30">
            <Bot size={16} className="text-white" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-violet-900">Video Analysis Chat</h2>
            <p className="text-xs text-violet-500">Ask questions about both videos</p>
          </div>
        </div>
        <div className={`flex items-center gap-2 text-xs font-semibold px-3 py-1.5 rounded-full ${
          isReady
            ? 'text-emerald-600 bg-emerald-50 border border-emerald-200'
            : 'text-violet-400 bg-violet-50 border border-violet-200'
        }`}>
          <span className={`w-2 h-2 rounded-full ${isReady ? 'bg-emerald-500' : 'bg-violet-400'}`} />
          {isReady ? 'Ready' : 'Waiting'}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-5 py-5 bg-gradient-to-b from-white/50 to-violet-50/30">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center gap-4 select-none">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-100 to-purple-100 border border-violet-200 flex items-center justify-center shadow-lg">
              <MessageCircle size={28} className="text-violet-400" />
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-violet-800 mb-1">Ready to compare videos</p>
              <p className="text-xs text-violet-500 max-w-xs">
                Ask anything about the video content, engagement metrics, creator styles, or performance comparison.
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs text-violet-400 bg-violet-100 px-3 py-1.5 rounded-full mt-2">
              <Sparkles size={12} className="text-violet-500" />
              <span>RAG-powered analysis</span>
            </div>
          </div>
        ) : (
          <>
            {messages.map(msg => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </>
        )}
      </div>

      <div className="px-4 py-4 border-t border-violet-100 flex-shrink-0 bg-white/60">
        <div className={`flex items-center gap-3 rounded-xl border px-4 py-2.5 transition-all ${
          isReady
            ? 'bg-violet-50/50 border-violet-200 focus-within:border-violet-400 focus-within:ring-2 focus-within:ring-violet-400/20'
            : 'bg-violet-50/30 border-violet-100 opacity-50'
        }`}>
          <input
            ref={inputRef}
            type="text"
            placeholder={isReady ? 'Ask about the videos…' : 'Waiting for processing…'}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!isReady || isSending}
            className="flex-1 bg-transparent text-sm text-violet-900 placeholder:text-violet-400 outline-none disabled:cursor-not-allowed"
          />
          <button
            onClick={sendMessage}
            disabled={!isReady || isSending || !input.trim()}
            className="w-9 h-9 rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 hover:from-violet-500 hover:to-purple-500 text-white flex items-center justify-center transition-all disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0 shadow-lg shadow-violet-400/30"
            aria-label="Send"
          >
            {isSending ? (
              <div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
            ) : (
              <Send size={15} />
            )}
          </button>
        </div>
        <p className="text-[10px] text-violet-400 mt-2 px-1">Press Enter to send</p>
      </div>
    </div>
  );
}

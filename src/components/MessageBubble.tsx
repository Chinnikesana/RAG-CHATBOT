export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  isStreaming?: boolean;
}

interface MessageBubbleProps {
  message: Message;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[85%] ${isUser ? 'items-end' : 'items-start'} flex flex-col gap-1.5`}>
        <div className="flex items-center gap-2 px-1">
          <span className={`text-[10px] font-bold tracking-wider uppercase ${isUser ? 'text-violet-600' : 'text-violet-400'}`}>
            {isUser ? 'You' : 'Assistant'}
          </span>
        </div>

        <div
          className={`
            px-4 py-3 rounded-2xl text-sm leading-relaxed
            ${isUser
              ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-tr-sm shadow-lg shadow-violet-400/20'
              : 'bg-white text-violet-900 rounded-tl-sm border border-violet-200 shadow-md'
            }
          `}
        >
          <span>{message.content}</span>
          {message.isStreaming && (
            <span className="cursor-blink" aria-hidden="true" />
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="flex flex-wrap gap-1.5 px-1">
            {message.sources.map((source, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 text-[10px] font-semibold text-violet-600 bg-violet-100 border border-violet-200 rounded-full px-2.5 py-0.5"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-violet-500" />
                {source}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

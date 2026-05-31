import { Eye, Heart, MessageCircle, Clock, Users, Calendar, Zap, Youtube, Instagram } from 'lucide-react';

export interface VideoMeta {
  video_id: string;
  platform: 'youtube' | 'instagram';
  title: string;
  creator: string;
  followers: number;
  upload_date: string;
  duration: number;
  views: number;
  likes: number;
  comments: number;
  hashtags: string[];
  engagement_rate: number;
  transcript_chunks: number;
  url?: string;
  thumbnail?: string;
}

interface VideoCardProps {
  video: VideoMeta;
  label: 'Video A' | 'Video B';
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function getYouTubeId(url?: string): string | null {
  if (!url) return null;
  const match = url.match(/(?:v=|youtu\.be\/|\/shorts\/)([A-Za-z0-9_-]{11})/);
  return match ? match[1] : null;
}

export default function VideoCard({ video, label }: VideoCardProps) {
  const isYouTube = video.platform === 'youtube';
  const ytId = isYouTube ? getYouTubeId(video.url) : null;
  const isVideoA = label === 'Video A';
  const badgeColors = isVideoA
    ? 'bg-violet-100 text-violet-700 border-violet-200'
    : 'bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200';

  return (
    <div className="rounded-2xl border border-violet-200/70 bg-white/90 shadow-lg shadow-violet-900/5 overflow-hidden">
      <div className="relative aspect-video bg-gradient-to-br from-violet-100 to-purple-100">
        {isYouTube && ytId ? (
          <iframe
            src={`https://www.youtube.com/embed/${ytId}?modestbranding=1&rel=0`}
            className="w-full h-full"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            title={video.title}
          />
        ) : video.thumbnail ? (
          <img src={video.thumbnail} alt={video.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-pink-100 to-violet-100">
            <div className="w-12 h-12 rounded-full bg-gradient-to-br from-pink-400 to-violet-400 flex items-center justify-center shadow-lg">
              <Instagram size={20} className="text-white" />
            </div>
            <span className="text-xs text-violet-600/70 font-medium">Instagram Reel</span>
          </div>
        )}

        <span className={`absolute top-3 right-3 text-[10px] font-bold px-2.5 py-1 rounded-full border ${badgeColors}`}>
          {label}
        </span>

        <span className="absolute bottom-3 right-3 text-[11px] font-semibold bg-black/60 text-white px-2 py-0.5 rounded-md backdrop-blur-sm">
          {formatDuration(video.duration)}
        </span>

        <div className={`absolute top-3 left-3 w-7 h-7 rounded-lg flex items-center justify-center shadow-md ${
          isYouTube ? 'bg-red-500' : 'bg-gradient-to-br from-pink-500 to-purple-500'
        }`}>
          {isYouTube ? (
            <Youtube size={14} className="text-white" />
          ) : (
            <Instagram size={14} className="text-white" />
          )}
        </div>
      </div>

      <div className="p-4 space-y-3">
        <div>
          <h3 className="text-sm font-bold text-violet-950 leading-snug line-clamp-2">{video.title}</h3>
          <div className="flex items-center gap-1.5 mt-2">
            <span className="text-xs font-semibold text-violet-700">{video.creator}</span>
            <span className="w-px h-3 bg-violet-300" />
            <Users size={11} className="text-violet-400" />
            <span className="text-xs text-violet-500">
              {video.followers > 0 ? `${formatNumber(video.followers)} followers` : 'N/A'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <Stat icon={<Eye size={12} />} value={formatNumber(video.views)} label="Views" color="violet" />
          <Stat icon={<Heart size={12} />} value={formatNumber(video.likes)} label="Likes" color="pink" />
          <Stat icon={<MessageCircle size={12} />} value={formatNumber(video.comments)} label="Comments" color="fuchsia" />
        </div>

        <div className="flex items-center justify-between pt-2.5 border-t border-violet-100">
          <div className="flex items-center gap-1.5 text-violet-500">
            <Calendar size={12} />
            <span className="text-[11px] font-medium">{video.upload_date}</span>
          </div>
          <div className="flex items-center gap-1.5 bg-gradient-to-r from-violet-100 to-purple-100 px-2.5 py-1 rounded-full">
            <Zap size={11} className="text-violet-500" />
            <span className="text-[11px] font-bold text-violet-700">{video.engagement_rate.toFixed(2)}%</span>
            <span className="text-[10px] text-violet-500">engagement</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function Stat({ icon, value, label, color }: { icon: React.ReactNode; value: string; label: string; color: 'violet' | 'pink' | 'fuchsia' }) {
  const bgColors = {
    violet: 'bg-violet-50 border-violet-100',
    pink: 'bg-pink-50 border-pink-100',
    fuchsia: 'bg-fuchsia-50 border-fuchsia-100',
  };
  const iconColors = {
    violet: 'text-violet-500',
    pink: 'text-pink-500',
    fuchsia: 'text-fuchsia-500',
  };
  const textColors = {
    violet: 'text-violet-700',
    pink: 'text-pink-700',
    fuchsia: 'text-fuchsia-700',
  };

  return (
    <div className={`flex flex-col items-center gap-1 rounded-xl py-2.5 border ${bgColors[color]}`}>
      <div className={iconColors[color]}>{icon}</div>
      <span className={`text-xs font-bold ${textColors[color]}`}>{value}</span>
      <span className="text-[10px] text-violet-400 font-medium">{label}</span>
    </div>
  );
}

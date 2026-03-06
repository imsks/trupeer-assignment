import { useCallback, useRef } from "react";
import { usePlayerStore } from "../../store/playerStore";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
}

export default function PlaybackControls({ onTogglePlay, onSeek }: Props) {
  const currentTime = usePlayerStore((s) => s.currentTime);
  const duration = usePlayerStore((s) => s.duration);
  const isPlaying = usePlayerStore((s) => s.isPlaying);
  const timelineRef = useRef<HTMLDivElement>(null);

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  const handleTimelineClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = timelineRef.current?.getBoundingClientRect();
      if (!rect || duration <= 0) return;
      const x = (e.clientX - rect.left) / rect.width;
      onSeek(Math.max(0, Math.min(1, x)) * duration);
    },
    [duration, onSeek],
  );

  const handleTimelineDrag = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (e.buttons !== 1) return;
      handleTimelineClick(e);
    },
    [handleTimelineClick],
  );

  const intervals = duration > 0 ? Math.ceil(duration / 15) : 0;
  const ticks = Array.from({ length: intervals + 1 }, (_, i) =>
    Math.min(i * 15, duration),
  );

  return (
    <div className="px-6 py-4 flex flex-col gap-2">
      <div className="flex items-center gap-4">
        <button
          onClick={onTogglePlay}
          className="w-10 h-10 rounded-full bg-indigo-500 hover:bg-indigo-600 text-white flex items-center justify-center transition-colors shrink-0"
          aria-label={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? (
            <svg width="14" height="16" viewBox="0 0 14 16" fill="currentColor">
              <rect x="1" y="0" width="4" height="16" rx="1" />
              <rect x="9" y="0" width="4" height="16" rx="1" />
            </svg>
          ) : (
            <svg width="14" height="16" viewBox="0 0 14 16" fill="currentColor">
              <polygon points="2,0 14,8 2,16" />
            </svg>
          )}
        </button>
        <span className="text-sm text-gray-600 font-mono tabular-nums min-w-[100px]">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>

      <div className="flex flex-col gap-1">
        <div
          ref={timelineRef}
          className="relative h-2 bg-gray-200 rounded-full cursor-pointer group"
          onClick={handleTimelineClick}
          onMouseMove={handleTimelineDrag}
        >
          <div
            className="absolute inset-y-0 left-0 bg-indigo-500 rounded-full transition-[width] duration-75"
            style={{ width: `${progress}%` }}
          />
          <div
            className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 bg-indigo-600 rounded-full shadow-md border-2 border-white transition-[left] duration-75"
            style={{ left: `calc(${progress}% - 7px)` }}
          />
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 select-none">
          {ticks.map((t) => (
            <span key={t}>{formatTime(t)}</span>
          ))}
        </div>
      </div>
    </div>
  );
}

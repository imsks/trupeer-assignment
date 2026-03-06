import { useEffect, useState } from "react";
import Layout from "./components/Layout";
import Player from "./components/Player";
import Sidebar from "./components/Sidebar";
import { useTranscript } from "./hooks/useTranscript";
import { useVideoPlayer } from "./hooks/useVideoPlayer";
import { fetchVideoMetadata } from "./api/mockApi";
import type { VideoMetadata } from "./types";

export default function App() {
  const { transcript, loading, error } = useTranscript();
  const [meta, setMeta] = useState<VideoMetadata | null>(null);

  const words = transcript?.words ?? [];
  const { videoRef, initVideo, seek, togglePlayPause } = useVideoPlayer(words);
  const [videoReady, setVideoReady] = useState(false);

  useEffect(() => {
    fetchVideoMetadata().then(setMeta);
  }, []);

  useEffect(() => {
    if (!meta) return;
    const el = initVideo(meta.src);
    el.addEventListener("canplay", () => setVideoReady(true), { once: true });
  }, [meta, initVideo]);

  if (loading || !meta) {
    return (
      <div className="flex items-center justify-center h-screen w-screen bg-gray-50">
        <div className="text-gray-400 text-sm">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-screen w-screen bg-gray-50">
        <div className="text-red-500 text-sm">Error: {error}</div>
      </div>
    );
  }

  return (
    <Layout
      sidebar={<Sidebar words={words} onSeek={seek} />}
      player={
        <Player
          videoElement={videoReady ? videoRef.current : null}
          backgroundSrc={meta.backgroundSrc}
          onTogglePlay={togglePlayPause}
          onSeek={seek}
        />
      }
    />
  );
}

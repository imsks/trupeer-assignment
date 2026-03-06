import ThreeScene from "./ThreeScene";
import PlaybackControls from "./PlaybackControls";

interface Props {
  videoElement: HTMLVideoElement | null;
  backgroundSrc: string;
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
}

export default function Player({
  videoElement,
  backgroundSrc,
  onTogglePlay,
  onSeek,
}: Props) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 relative min-h-0">
        <ThreeScene
          videoElement={videoElement}
          backgroundSrc={backgroundSrc}
        />
      </div>
      <PlaybackControls onTogglePlay={onTogglePlay} onSeek={onSeek} />
    </div>
  );
}

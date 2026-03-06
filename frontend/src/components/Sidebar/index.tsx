import Transcript from "./Transcript";
import SliderControl from "./SliderControl";
import { usePlayerStore } from "../../store/playerStore";
import type { Word } from "../../types";

interface Props {
  words: Word[];
  onSeek: (time: number) => void;
}

export default function Sidebar({ words, onSeek }: Props) {
  const padding = usePlayerStore((s) => s.padding);
  const rounding = usePlayerStore((s) => s.rounding);
  const setPadding = usePlayerStore((s) => s.setPadding);
  const setRounding = usePlayerStore((s) => s.setRounding);

  return (
    <div className="flex flex-col h-full bg-white border-r border-gray-100">
      <div className="flex-1 min-h-0 overflow-hidden">
        <Transcript words={words} onSeek={onSeek} />
      </div>
      <div className="border-t border-gray-100">
        <SliderControl
          label="Padding"
          value={padding}
          min={0}
          max={32}
          onChange={setPadding}
        />
        <SliderControl
          label="Rounding"
          value={rounding}
          min={0}
          max={32}
          onChange={setRounding}
        />
      </div>
    </div>
  );
}

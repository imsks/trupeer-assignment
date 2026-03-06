import { memo, useCallback, useEffect, useRef, useState } from "react";
import type { Word } from "../../types";
import { usePlayerStore } from "../../store/playerStore";

interface WordSpanProps {
  word: Word;
  index: number;
  isActive: boolean;
  isSkipped: boolean;
  onClickWord: (index: number) => void;
}

const WordSpan = memo(function WordSpan({
  word,
  index,
  isActive,
  isSkipped,
  onClickWord,
}: WordSpanProps) {
  if (word.type === "spacing") {
    return <span>{word.text}</span>;
  }

  return (
    <span
      data-word-index={index}
      onClick={() => onClickWord(index)}
      className={[
        "cursor-pointer rounded-sm px-[1px] transition-colors duration-100",
        isActive ? "bg-indigo-200 text-indigo-900" : "",
        isSkipped ? "line-through text-gray-400" : "",
      ].join(" ")}
    >
      {word.text}
    </span>
  );
});

interface Props {
  words: Word[];
  onSeek: (time: number) => void;
}

export default function Transcript({ words, onSeek }: Props) {
  const currentWordIndex = usePlayerStore((s) => s.currentWordIndex);
  const skippedIndices = usePlayerStore((s) => s.skippedIndices);
  const toggleSkip = usePlayerStore((s) => s.toggleSkip);

  const containerRef = useRef<HTMLDivElement>(null);
  const [selectedRange, setSelectedRange] = useState<number[] | null>(null);

  useEffect(() => {
    if (currentWordIndex < 0) return;
    const el = containerRef.current?.querySelector(
      `[data-word-index="${currentWordIndex}"]`,
    );
    if (el) {
      el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [currentWordIndex]);

  const handleClickWord = useCallback(
    (index: number) => {
      const w = words[index];
      if (w && w.type === "word") {
        onSeek(w.start);
      }
    },
    [words, onSeek],
  );

  const handleMouseUp = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !containerRef.current) {
      setSelectedRange(null);
      return;
    }

    const range = sel.getRangeAt(0);
    const spans = containerRef.current.querySelectorAll("[data-word-index]");
    const indices: number[] = [];

    spans.forEach((span) => {
      if (range.intersectsNode(span)) {
        const idx = Number(span.getAttribute("data-word-index"));
        if (!isNaN(idx) && words[idx]?.type === "word") {
          indices.push(idx);
        }
      }
    });

    if (indices.length > 0) {
      setSelectedRange(indices);
    } else {
      setSelectedRange(null);
    }
  }, [words]);

  const handleSkipToggle = useCallback(() => {
    if (!selectedRange) return;
    toggleSkip(selectedRange);
    setSelectedRange(null);
    window.getSelection()?.removeAllRanges();
  }, [selectedRange, toggleSkip]);

  const allSelectedAreSkipped =
    selectedRange?.every((i) => skippedIndices.has(i)) ?? false;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <h2 className="text-sm font-semibold text-gray-800">Script</h2>
        {selectedRange && selectedRange.length > 0 && (
          <button
            onClick={handleSkipToggle}
            className="text-xs px-3 py-1 rounded-md bg-indigo-50 text-indigo-600 hover:bg-indigo-100 transition-colors font-medium flex items-center gap-1"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M5 4l10 8-10 8V4z" />
              <line x1="19" y1="5" x2="19" y2="19" />
            </svg>
            {allSelectedAreSkipped ? "Unskip" : "Skip"}
          </button>
        )}
      </div>
      <div
        ref={containerRef}
        onMouseUp={handleMouseUp}
        className="flex-1 overflow-y-auto px-4 py-3 text-sm leading-relaxed text-gray-700 will-change-scroll"
      >
        {words.map((word, i) => (
          <WordSpan
            key={i}
            word={word}
            index={i}
            isActive={i === currentWordIndex}
            isSkipped={skippedIndices.has(i)}
            onClickWord={handleClickWord}
          />
        ))}
      </div>
    </div>
  );
}

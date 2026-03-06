import { create } from "zustand";

interface PlayerState {
  currentTime: number;
  duration: number;
  isPlaying: boolean;
  padding: number;
  rounding: number;
  skippedIndices: Set<number>;
  currentWordIndex: number;

  setCurrentTime: (t: number) => void;
  setDuration: (d: number) => void;
  setIsPlaying: (p: boolean) => void;
  setPadding: (p: number) => void;
  setRounding: (r: number) => void;
  toggleSkip: (indices: number[]) => void;
  setCurrentWordIndex: (i: number) => void;
}

export const usePlayerStore = create<PlayerState>((set, get) => ({
  currentTime: 0,
  duration: 0,
  isPlaying: false,
  padding: 0,
  rounding: 0,
  skippedIndices: new Set(),
  currentWordIndex: -1,

  setCurrentTime: (t) => set({ currentTime: t }),
  setDuration: (d) => set({ duration: d }),
  setIsPlaying: (p) => set({ isPlaying: p }),
  setPadding: (p) => set({ padding: p }),
  setRounding: (r) => set({ rounding: r }),

  toggleSkip: (indices) => {
    const current = get().skippedIndices;
    const next = new Set(current);
    const allSkipped = indices.every((i) => current.has(i));
    if (allSkipped) {
      indices.forEach((i) => next.delete(i));
    } else {
      indices.forEach((i) => next.add(i));
    }
    set({ skippedIndices: next });
  },

  setCurrentWordIndex: (i) => set({ currentWordIndex: i }),
}));

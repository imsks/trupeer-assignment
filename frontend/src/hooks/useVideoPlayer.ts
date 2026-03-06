import { useCallback, useEffect, useRef } from "react";
import { usePlayerStore } from "../store/playerStore";
import type { Word } from "../types";

export function useVideoPlayer(words: Word[]) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const rafRef = useRef<number>(0);
  const lastWordIdx = useRef(-1);

  const setCurrentTime = usePlayerStore((s) => s.setCurrentTime);
  const setDuration = usePlayerStore((s) => s.setDuration);
  const setIsPlaying = usePlayerStore((s) => s.setIsPlaying);
  const setCurrentWordIndex = usePlayerStore((s) => s.setCurrentWordIndex);

  const initVideo = useCallback((src: string) => {
    if (videoRef.current) return videoRef.current;
    const el = document.createElement("video");
    el.src = src;
    el.crossOrigin = "anonymous";
    el.playsInline = true;
    el.preload = "auto";
    el.muted = false;
    videoRef.current = el;

    el.addEventListener("loadedmetadata", () => {
      setDuration(el.duration);
    });

    el.addEventListener("ended", () => {
      setIsPlaying(false);
    });

    return el;
  }, [setDuration, setIsPlaying]);

  const findWordIndex = useCallback(
    (time: number): number => {
      if (!words.length) return -1;
      let lo = 0;
      let hi = words.length - 1;
      let result = -1;
      while (lo <= hi) {
        const mid = (lo + hi) >> 1;
        const w = words[mid];
        if (w.type !== "word") {
          if (w.start <= time) lo = mid + 1;
          else hi = mid - 1;
          continue;
        }
        if (time >= w.start && time <= w.end) return mid;
        if (w.start > time) hi = mid - 1;
        else {
          result = mid;
          lo = mid + 1;
        }
      }
      return result;
    },
    [words],
  );

  const tick = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    const t = video.currentTime;
    setCurrentTime(t);

    const idx = findWordIndex(t);
    if (idx !== lastWordIdx.current) {
      lastWordIdx.current = idx;
      setCurrentWordIndex(idx);
    }

    const skipped = usePlayerStore.getState().skippedIndices;
    if (skipped.size > 0 && idx >= 0 && skipped.has(idx)) {
      let next = idx + 1;
      while (next < words.length && (skipped.has(next) || words[next].type !== "word")) {
        next++;
      }
      if (next < words.length) {
        video.currentTime = words[next].start;
      } else {
        video.pause();
        setIsPlaying(false);
      }
    }

    rafRef.current = requestAnimationFrame(tick);
  }, [findWordIndex, setCurrentTime, setCurrentWordIndex, setIsPlaying, words]);

  const play = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.play();
    setIsPlaying(true);
    rafRef.current = requestAnimationFrame(tick);
  }, [tick, setIsPlaying]);

  const pause = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    video.pause();
    setIsPlaying(false);
    cancelAnimationFrame(rafRef.current);
  }, [setIsPlaying]);

  const seek = useCallback(
    (time: number) => {
      const video = videoRef.current;
      if (!video) return;
      video.currentTime = time;
      setCurrentTime(time);
      const idx = findWordIndex(time);
      lastWordIdx.current = idx;
      setCurrentWordIndex(idx);
    },
    [findWordIndex, setCurrentTime, setCurrentWordIndex],
  );

  const togglePlayPause = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) play();
    else pause();
  }, [play, pause]);

  useEffect(() => {
    return () => {
      cancelAnimationFrame(rafRef.current);
      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.src = "";
        videoRef.current.load();
      }
    };
  }, []);

  return { videoRef, initVideo, play, pause, seek, togglePlayPause };
}

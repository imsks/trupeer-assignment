import type { Transcript, VideoMetadata } from "../types";

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchTranscript(): Promise<Transcript> {
  await delay(300);
  const res = await fetch("/transcript.json");
  if (!res.ok) throw new Error("Failed to fetch transcript");
  return res.json();
}

export async function fetchVideoMetadata(): Promise<VideoMetadata> {
  await delay(200);
  return {
    src: "/video.mp4",
    backgroundSrc: "/background.jpg",
    duration: 200,
  };
}

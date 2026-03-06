from __future__ import annotations

from worker.processors.base import BaseProcessor


class OverlayProcessor(BaseProcessor):
    """Burn .srt subtitles into a video using ffmpeg."""

    def output_filename(self) -> str:
        return "output.mp4"

    def build_command(self, input_path: str, output_path: str, **kwargs) -> list[str]:
        subtitle_path = kwargs["subtitle_path"]
        return [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", f"subtitles={subtitle_path}",
            "-c:a", "copy",
            output_path,
        ]

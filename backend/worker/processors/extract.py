from __future__ import annotations

from worker.processors.base import BaseProcessor


class ExtractProcessor(BaseProcessor):
    """Extract audio from video and encode to mp3."""

    def output_filename(self) -> str:
        return "output.mp3"

    def build_command(self, input_path: str, output_path: str, **kwargs) -> list[str]:
        return [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            output_path,
        ]

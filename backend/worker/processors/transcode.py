from __future__ import annotations

from worker.processors.base import BaseProcessor


class TranscodeProcessor(BaseProcessor):
    """Downscale video to 480p using ffmpeg."""

    def output_filename(self) -> str:
        return "output.mp4"

    def build_command(self, input_path: str, output_path: str, **kwargs) -> list[str]:
        return [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", "scale=-2:480",
            "-c:a", "copy",
            output_path,
        ]

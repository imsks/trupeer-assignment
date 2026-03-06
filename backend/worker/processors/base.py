from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Callable, Optional

import structlog

logger = structlog.get_logger()


class BaseProcessor(ABC):
    """Base class for ffmpeg-based media processors."""

    def __init__(self, job_id: str, work_dir: str):
        self.job_id = job_id
        self.work_dir = work_dir
        os.makedirs(work_dir, exist_ok=True)

    @abstractmethod
    def build_command(self, input_path: str, output_path: str, **kwargs) -> list[str]:
        """Return the ffmpeg command as a list of arguments."""
        ...

    @abstractmethod
    def output_filename(self) -> str:
        """Return the expected output filename."""
        ...

    async def execute(
        self,
        input_path: str,
        progress_callback: Optional[Callable] = None,
        **kwargs,
    ) -> str:
        output_path = os.path.join(self.work_dir, self.output_filename())
        cmd = self.build_command(input_path, output_path, **kwargs)
        logger.info("ffmpeg_start", job_id=self.job_id, cmd=" ".join(cmd))

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode(errors="replace")[-2000:]
            logger.error("ffmpeg_failed", job_id=self.job_id, returncode=process.returncode, stderr=error_msg)
            raise RuntimeError(f"ffmpeg exited with code {process.returncode}: {error_msg}")

        if not os.path.exists(output_path):
            raise RuntimeError(f"Expected output not found: {output_path}")

        logger.info("ffmpeg_done", job_id=self.job_id, output=output_path)
        return output_path

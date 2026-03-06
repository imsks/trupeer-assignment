from __future__ import annotations

import os
import uuid


def get_worker_id() -> str:
    return os.getenv("WORKER_ID", f"worker-{uuid.uuid4().hex[:8]}")


def get_tmp_dir() -> str:
    return os.getenv("WORKER_TMP_DIR", "/tmp/media-worker")

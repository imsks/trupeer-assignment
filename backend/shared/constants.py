from enum import StrEnum


class JobType(StrEnum):
    OVERLAY = "overlay"
    TRANSCODE = "transcode"
    EXTRACT = "extract"


class JobStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class WorkerStatus(StrEnum):
    ALIVE = "alive"
    DEAD = "dead"


REDIS_STREAM_JOBS = "media:jobs"
REDIS_CONSUMER_GROUP = "media:workers"
REDIS_HEARTBEAT_KEY = "workers:heartbeat"
REDIS_WORKER_META_PREFIX = "worker:meta:"

JOB_PROGRESS_CHANNEL_PREFIX = "job:progress:"

MINIO_INPUT_PREFIX = "inputs"
MINIO_OUTPUT_PREFIX = "outputs"

MAX_JOB_RETRIES = 3
HEARTBEAT_INTERVAL_SEC = 5
HEARTBEAT_TIMEOUT_SEC = 15
DEAD_MESSAGE_IDLE_MS = 60_000

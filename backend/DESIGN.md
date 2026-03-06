# Design Document: Distributed Media Pipeline

## 1. Overview

This system is a distributed media processing engine that coordinates a pool of Worker Nodes to perform video operations via ffmpeg. A central API Gateway accepts jobs, distributes them across workers through Redis Streams, and provides real-time progress via Server-Sent Events. An agentic orchestration layer allows natural language instructions to be decomposed into multi-step processing pipelines.

## 2. Architecture

```
                                    ┌─────────────────┐
                                    │   Client / Demo │
                                    │    Scripts      │
                                    └────────┬────────┘
                                             │ HTTP / SSE
                                    ┌────────▼─────────┐
                              ┌─────│   API Gateway    │─────┐
                              │     │   (FastAPI)      │     │
                              │     └────────┬─────────┘     │
                              │              │               │
                    ┌─────────▼──┐   ┌──────▼──────┐   ┌───▼──────────┐
                    │ PostgreSQL  │   │   Redis 7    │   │   MinIO       │
                    │ (Job State) │   │ (Streams +   │   │ (S3-compat   │
                    │             │   │  Pub/Sub +   │   │  Object      │
                    │             │   │  Heartbeats) │   │  Storage)    │
                    └─────────────┘   └──────┬──────┘   └───┬──────────┘
                                             │               │
                              ┌──────────────┼───────────────┤
                              │              │               │
                     ┌────────▼──┐  ┌────────▼──┐  ┌────────▼──┐
                     │ Worker 1   │  │ Worker 2   │  │ Worker N   │
                     │ (ffmpeg)   │  │ (ffmpeg)   │  │ (ffmpeg)   │
                     └────────────┘  └────────────┘  └────────────┘
```

### Component Responsibilities

| Component      | Role                                                                                     |
| -------------- | ---------------------------------------------------------------------------------------- |
| **Gateway**    | HTTP API, file upload, job state management, SSE streaming, orchestrator background loop |
| **Redis**      | Job queue (Streams), worker heartbeats (Sorted Sets), real-time events (Pub/Sub)         |
| **PostgreSQL** | Persistent job metadata, state machine, retry counts, pipeline tracking                  |
| **MinIO**      | Durable object storage for input/output media files with presigned URL access            |
| **Workers**    | Stateless ffmpeg executors, pull jobs from Redis consumer group, upload results to MinIO |

## 3. Key Design Decisions

### 3.1 Why Redis Streams over RabbitMQ or Kafka

Redis Streams provide consumer group semantics (competing consumers, message acknowledgment, pending entry list) without requiring a separate message broker. For a video processing workload where throughput is bounded by ffmpeg speed (not message throughput), Redis Streams are the right weight class:

- **Built-in consumer groups**: `XREADGROUP` gives us competing consumers with automatic load balancing.
- **Pending Entry List (PEL)**: Unacknowledged messages are tracked per-consumer, enabling `XAUTOCLAIM` for crash recovery.
- **No extra infrastructure**: Redis already serves as our heartbeat store and pub/sub broker. One fewer service to operate.
- **Trade-off**: Redis Streams don't persist to disk as durably as Kafka. Acceptable here because job state lives in PostgreSQL -- the stream is a work queue, not the source of truth.

### 3.2 Why MinIO over Local Volume Mounts

Shared volume mounts (Docker bind mounts or named volumes) would create tight coupling between containers and wouldn't work across multiple hosts. MinIO gives us:

- **S3-compatible API**: Drop-in replacement for AWS S3 in production. Zero code changes to move from local dev to cloud.
- **Presigned URLs**: Clients can download output directly from MinIO without proxying through the gateway. This is critical for large video files.
- **Decoupled storage**: Workers can run on any host. No NFS, no shared filesystem assumptions.
- **Trade-off**: Adds network I/O (download input -> process -> upload output). For video files this is negligible compared to ffmpeg processing time.

### 3.3 Why PostgreSQL for Job State (not just Redis)

Redis is fast but isn't designed for complex queries, historical analytics, or transactional state machines:

- Jobs need a state machine with transitions (PENDING -> QUEUED -> PROCESSING -> COMPLETED/FAILED).
- We need to query by status, pipeline_id, creation time, and support pagination.
- Retry counts and error logs need durable storage.
- PostgreSQL's ACID guarantees prevent race conditions on state transitions.

### 3.4 Workers are Stateless and DB-Free

Workers intentionally have **no direct database access**. All context they need arrives via the Redis Stream message (job_id, job_type, file paths). They report progress via Redis Pub/Sub. This design means:

- Workers can be scaled to any number without DB connection pool pressure.
- Worker code is simpler -- no ORM, no migrations, no connection management.
- Gateway is the single source of truth for job state.
- Trade-off: Workers can't update DB directly if gateway is down. Acceptable because gateway unavailability means no new jobs are being created anyway.

## 4. Data Flow

### Job Submission

1. Client POSTs multipart form to `/api/v1/jobs` with video file + job type.
2. Gateway generates a job UUID and uploads the input file to MinIO at `inputs/{job_id}/filename`.
3. Gateway creates a Job row in PostgreSQL (status=PENDING).
4. Gateway pushes a message to Redis Stream `media:jobs` containing job_id, job_type, and file paths as metadata.
5. Gateway transitions the job to QUEUED and returns the job object to the client.

### Worker Processing

1. Worker blocks on `XREADGROUP` waiting for new messages.
2. On claim, worker publishes PROCESSING status to Redis Pub/Sub channel `job:progress:{job_id}`.
3. Worker downloads input from MinIO to local `/tmp/{job_id}/`.
4. Worker runs the appropriate ffmpeg command (overlay, transcode, or extract).
5. Worker uploads the output to MinIO at `outputs/{job_id}/filename`.
6. Worker sends `XACK` to acknowledge the message.
7. Worker publishes COMPLETED status to Redis Pub/Sub.

### Client Retrieval

- **Polling**: `GET /api/v1/jobs/{id}` returns current state from PostgreSQL.
- **Real-time**: `GET /api/v1/jobs/{id}/status` returns an SSE stream. Gateway subscribes to Redis Pub/Sub channel for the job and forwards events.
- **Download**: `GET /api/v1/jobs/{id}/output` generates a presigned MinIO URL (1hr TTL) for direct download.

## 5. Elastic Orchestration

### Worker Discovery

Workers are **self-registering**. On startup, each worker begins writing to a Redis Sorted Set `workers:heartbeat` every 5 seconds, with the score set to the current Unix timestamp. No manual registration required.

### Health Monitoring

The gateway runs a background orchestrator loop every 10 seconds:

1. Query `workers:heartbeat` sorted set for entries with score < (now - 15s).
2. Any worker whose heartbeat is stale is considered DEAD.
3. For dead workers, run `XAUTOCLAIM` on the consumer group to reclaim their pending messages.
4. Reclaimed jobs are checked against their retry budget (max 3 attempts). If exceeded, moved to DEAD_LETTER.

### Scaling

```bash
docker-compose up --scale worker=5
```

New workers automatically join the Redis consumer group and begin claiming messages. Redis handles load distribution across consumers. No configuration changes needed.

## 6. Resiliency and Recovery

| Failure Mode                    | Recovery Mechanism                                                                   |
| ------------------------------- | ------------------------------------------------------------------------------------ |
| Worker crashes mid-processing   | Message stays in PEL. `XAUTOCLAIM` reclaims it after 60s idle timeout.               |
| Worker process killed (SIGKILL) | Same as crash -- heartbeat stops, orchestrator detects death, reclaims messages.     |
| Gateway restarts                | Job state is in PostgreSQL. Consumer group state is in Redis. Both survive restarts. |
| Redis restarts                  | Stream data persists (AOF/RDB). Consumer groups are recreated on gateway startup.    |
| MinIO restarts                  | Object data persists on volume. Upload/download retries handle transient failures.   |
| Duplicate processing            | Workers check if output already exists in MinIO before processing (idempotency).     |
| Repeated failures               | After 3 attempts, job moves to DEAD_LETTER for manual investigation.                 |

### Graceful Shutdown

Workers trap SIGTERM and set a stop event. The consumer loop finishes the current job before exiting, ensuring in-flight work is completed and acknowledged before shutdown.

## 7. Agentic Orchestration

### Three-Tier Intent Parsing

To balance cost and latency, natural language instructions are parsed through three tiers:

1. **Regex Deterministic Match** (Tier 0): Common single-operation patterns ("add subtitles", "extract audio", "downscale") are matched via compiled regexes. Cost: $0. Latency: <1ms.
2. **Redis Pattern Cache** (Tier 1): Previously parsed instructions (normalized to lowercase) are cached as JSON in a Redis hash. LLM is only called on cache miss. Cost: $0 after first call. Latency: <5ms.
3. **LLM API Call** (Tier 2): Complex multi-step instructions are sent to GPT-4o-mini (or Claude Haiku) with a structured system prompt. The model returns a JSON array of pipeline steps. Cost: ~$0.0001/request. Latency: ~500ms.

### Why GPT-4o-mini / Haiku

Intent parsing is **structured extraction**, not open-ended reasoning. Small, fast models excel at this when given clear schemas and few-shot examples. Using GPT-4 or Claude Opus would cost 30x more with negligible quality improvement for this narrow task.

### Pipeline Execution

The agent endpoint decomposes an instruction into a list of `PipelineStep` objects, each with a `depends_on` field forming a DAG. Steps without dependencies are immediately enqueued. Dependent steps are enqueued when their parent completes (future enhancement: the orchestrator monitors pipeline progress and enqueues downstream steps).

### UX: Plan-Before-Execute

The `/agent/plan` endpoint returns the execution plan without running it. This enables:

- **Human-in-the-loop**: User reviews the plan before committing to a potentially expensive multi-step pipeline.
- **Cost preview**: Estimated duration is returned based on step count.
- **Confidence check**: If the LLM misinterprets the instruction, the user catches it before any processing begins.

## 8. Trade-offs and Limitations

| Decision                       | Benefit                                    | Cost                                                       |
| ------------------------------ | ------------------------------------------ | ---------------------------------------------------------- |
| At-least-once delivery         | No job is ever lost                        | Possible duplicate processing (mitigated by idempotency)   |
| Heartbeat-based discovery      | Simple, no service mesh needed             | Up to 15s delay to detect dead worker                      |
| Workers have no DB access      | Simpler workers, no connection pool issues | Gateway must be available for state updates                |
| Single Redis instance          | Simple deployment                          | SPOF for queue; mitigate with Redis Sentinel in production |
| LLM for complex intent parsing | Handles arbitrary natural language         | External API dependency, non-zero cost per request         |
| PostgreSQL for all job state   | ACID, rich queries, familiar tooling       | Slightly slower than pure-Redis state management           |

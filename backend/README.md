# Distributed Media Pipeline

A distributed media processing engine that coordinates a pool of Worker Nodes to perform video operations via ffmpeg. Built with FastAPI, Redis Streams, PostgreSQL, and MinIO.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [API Reference](#api-reference)
- [Demo Scripts](#demo-scripts)
- [Observability and Alerting](#observability-and-alerting)
- [Scale Strategy](#scale-strategy)
- [Agentic Orchestration](#agentic-orchestration)

---

## Quick Start

### Prerequisites

- Docker and Docker Compose (v2)
- (Optional) Python 3.12+ for running demo scripts locally

### Run the Stack

```bash
# Clone and navigate
cd assignment/backend

# Copy environment config
cp .env.example .env

# Build and launch all services (gateway, 2 workers, redis, postgres, minio)
docker-compose up --build

# Scale workers dynamically
docker-compose up --scale worker=5
```

The gateway is available at `http://localhost:8000`. The MinIO console is at `http://localhost:9001` (login: minioadmin / minioadmin123).

### Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"gateway"}

curl http://localhost:8000/api/v1/workers
# {"workers":[...],"total":2}
```

---

## Architecture

See [DESIGN.md](DESIGN.md) for the full architectural deep-dive with trade-off analysis.

**Summary:**

```
Client -> API Gateway (FastAPI) -> Redis Streams -> Worker Pool (ffmpeg)
                |                       |                  |
           PostgreSQL              Pub/Sub             MinIO (S3)
          (job state)           (real-time)         (file storage)
```

**Supported Job Types:**

| Type        | Operation                          | ffmpeg Command                                        |
|-------------|------------------------------------|-------------------------------------------------------|
| `overlay`   | Burn .srt subtitles into video     | `ffmpeg -i input.mp4 -vf subtitles=sub.srt output.mp4` |
| `transcode` | Downscale video to 480p            | `ffmpeg -i input.mp4 -vf scale=-2:480 output.mp4`      |
| `extract`   | Strip audio and encode to mp3      | `ffmpeg -i input.mp4 -vn -acodec libmp3lame output.mp3` |

---

## API Reference

### Submit a Job

```bash
# Transcode a video to 480p
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "job_type=transcode" \
  -F "video=@sample.mp4"

# Overlay subtitles
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "job_type=overlay" \
  -F "video=@sample.mp4" \
  -F "subtitle=@subtitles.srt"

# Extract audio
curl -X POST http://localhost:8000/api/v1/jobs \
  -F "job_type=extract" \
  -F "video=@sample.mp4"
```

**Response:**
```json
{
  "id": "a1b2c3d4-...",
  "job_type": "transcode",
  "status": "queued",
  "progress": 0,
  "created_at": "2026-03-06T10:00:00Z",
  "updated_at": "2026-03-06T10:00:00Z"
}
```

### Check Job Status

```bash
# Poll
curl http://localhost:8000/api/v1/jobs/{job_id}

# Real-time SSE stream
curl -N http://localhost:8000/api/v1/jobs/{job_id}/status
```

**SSE Events:**
```
event: status
data: {"job_id":"a1b2...","status":"processing","progress":30}

event: status
data: {"job_id":"a1b2...","status":"completed","progress":100}
```

### Download Output

```bash
curl http://localhost:8000/api/v1/jobs/{job_id}/output
# {"job_id":"...","download_url":"http://minio:9000/...?X-Amz-Signature=...","expires_in_seconds":3600}
```

### List Jobs

```bash
curl "http://localhost:8000/api/v1/jobs?status=completed&limit=10"
```

### Worker Pool Status

```bash
curl http://localhost:8000/api/v1/workers
# {"workers":[{"id":"worker-a3f8","status":"alive","last_heartbeat_age_sec":2.1,"current_job_id":"..."}],"total":2}
```

### Agent: Plan a Pipeline

```bash
curl -X POST http://localhost:8000/api/v1/agent/plan \
  -H "Content-Type: application/json" \
  -d '{"instruction": "downscale this video to 480p then extract the audio as mp3"}'
```

**Response:**
```json
{
  "instruction": "downscale this video to 480p then extract the audio as mp3",
  "steps": [
    {"step_index": 0, "job_type": "transcode", "params": {}, "depends_on": null},
    {"step_index": 1, "job_type": "extract", "params": {}, "depends_on": 0}
  ],
  "estimated_duration_seconds": 60,
  "requires_confirmation": true
}
```

### Agent: Execute a Pipeline

```bash
curl -X POST http://localhost:8000/api/v1/agent/execute \
  -F "instruction=add subtitles and then downscale to 480p" \
  -F "video=@sample.mp4" \
  -F "subtitle=@subtitles.srt"
```

---

## Demo Scripts

```bash
# Install httpx for demo scripts
pip install httpx

# Submit transcode job
python -m scripts.demo_submit_transcode --video sample.mp4

# Submit overlay job
python -m scripts.demo_submit_overlay --video sample.mp4 --subtitle sample.srt

# Submit extract job
python -m scripts.demo_submit_extract --video sample.mp4

# Plan-only agent query (no execution)
python -m scripts.demo_agent_query \
  --instruction "downscale to 480p then extract audio" \
  --video sample.mp4 \
  --plan-only

# Full agent execution
python -m scripts.demo_agent_query \
  --instruction "burn subtitles and then extract audio" \
  --video sample.mp4 \
  --subtitle subtitles.srt
```

---

## Observability and Alerting

### Structured Logging

All services use `structlog` for JSON-structured log output. Every log line includes:
- `job_id`, `worker_id` for correlation
- Event name (`job_enqueued`, `ffmpeg_start`, `job_completed`, `dead_worker_detected`)
- Timestamps and durations

This makes logs directly queryable in any log aggregation system (ELK, Loki, Datadog).

### Metrics (Production Recommendation)

Add a `/metrics` endpoint using `prometheus-fastapi-instrumentator` to expose:

| Metric                               | Type      | What It Tells You                                      |
|--------------------------------------|-----------|--------------------------------------------------------|
| `jobs_submitted_total`               | Counter   | Ingest rate by job type                                |
| `jobs_completed_total`               | Counter   | Throughput by job type                                 |
| `jobs_failed_total`                  | Counter   | Error rate -- spike = systemic issue                   |
| `job_processing_duration_seconds`    | Histogram | ffmpeg performance by job type                         |
| `worker_pool_size`                   | Gauge     | Active worker count from heartbeat set                 |
| `queue_depth`                        | Gauge     | Redis Stream length -- rising = workers can't keep up  |
| `queue_pending_messages`             | Gauge     | Unacknowledged messages -- rising = workers crashing   |

### Detecting Zombie Workers

A "zombie" worker is one that appears alive (heartbeat still running) but is stuck and not making progress on a job.

**Detection Strategy:**
1. Track `current_job_id` and `processing_start_time` in the worker's Redis hash metadata.
2. Gateway orchestrator checks: if a worker has been on the same job for >5 minutes (configurable per job type), flag it as a zombie.
3. Alert on `worker_zombie_detected` event.

**Remediation:**
- Force-reclaim the job via `XAUTOCLAIM`.
- Optionally send SIGTERM to the zombie container (requires Docker API access or Kubernetes pod eviction).

### Detecting Stuck Jobs

A job is "stuck" if it has been in `PROCESSING` state for longer than the expected maximum duration for its type.

**Detection Strategy:**
1. Gateway orchestrator queries PostgreSQL: `SELECT * FROM jobs WHERE status='processing' AND updated_at < NOW() - INTERVAL '5 minutes'`.
2. Jobs matching are candidates for requeue or dead-lettering.
3. Alert: `stuck_job_detected` with job_id, worker_id, and duration.

### Recommended Alerts

| Alert                              | Condition                                               | Severity |
|------------------------------------|---------------------------------------------------------|----------|
| Queue Depth High                   | Stream length > 100 for 5 min                           | Warning  |
| Worker Pool Shrunk                 | Active workers < 50% of expected replicas               | Critical |
| Dead Letter Queue Growing          | New dead_letter jobs in last 10 min                     | Critical |
| Job Processing Too Slow            | P95 processing time > 2x baseline                       | Warning  |
| Zombie Worker                      | Worker on same job > 5 min                              | Critical |
| Zero Workers Alive                 | Heartbeat set empty                                     | Critical |
| Gateway Error Rate                 | 5xx rate > 5% of requests                               | Critical |

---

## Scale Strategy

### Current Design (10 jobs/hour)

The current architecture handles low-to-moderate load comfortably:
- 2 worker replicas can process ~10 jobs/hour assuming 3-5min per video
- Single Redis instance, single PostgreSQL instance
- MinIO with local volume storage

### Scaling to 10,000 jobs/hour

At 10,000 jobs/hour (~167 jobs/min), several components need to evolve:

#### 1. Worker Tier: Horizontal Auto-Scaling

```
Current:  docker-compose --scale worker=2
Target:   Kubernetes Deployment with KEDA autoscaler
```

- Deploy workers as a Kubernetes Deployment with a HorizontalPodAutoscaler.
- Use [KEDA](https://keda.sh) to scale based on Redis Stream pending message count.
- Scale-to-zero when idle (cost savings), burst to 100+ workers during peaks.
- Workers are stateless -- scaling is trivial.

#### 2. Queue Tier: Redis Cluster

- Single Redis handles ~100K msg/s. Not the bottleneck at 10K jobs/hr.
- Still, deploy Redis in Sentinel or Cluster mode for HA (automatic failover if primary goes down).
- For extreme scale (100K+ jobs/hr), consider partitioning streams by job type: `media:jobs:overlay`, `media:jobs:transcode`, `media:jobs:extract`.

#### 3. Storage Tier: S3 + CDN

- Replace MinIO with AWS S3 (or keep MinIO on a dedicated cluster with erasure coding).
- Put a CloudFront CDN in front of output files. Presigned URLs still work; CDN caches reduce S3 egress costs.
- For inputs, consider direct-to-S3 uploads (presigned PUT URLs) to bypass gateway file proxying entirely.

#### 4. Database Tier: Read Replicas + Partitioning

- Add PostgreSQL read replicas for job listing/status queries.
- Partition the `jobs` table by `created_at` (monthly or weekly) to keep query performance constant.
- Consider moving high-frequency writes (progress updates) to Redis only, batching DB writes every 5 seconds.

#### 5. Gateway Tier: Multiple Instances

- Deploy 3+ gateway instances behind a load balancer.
- All gateway instances share the same PostgreSQL and Redis -- no affinity needed.
- SSE connections distribute across instances; each instance subscribes to the relevant Redis Pub/Sub channels independently.

#### Architecture at Scale

```
                    Load Balancer
                    /     |     \
              Gateway  Gateway  Gateway
                    \     |     /
              ┌─────────────────────┐
              │  Redis Cluster (HA) │
              └──────────┬──────────┘
              ┌──────────┴──────────┐
              │    Worker Pool      │
              │  (KEDA: 10-200)     │
              └──────────┬──────────┘
                    AWS S3 + CDN
```

---

## Agentic Orchestration

### Current Implementation

The system already supports agentic orchestration via the `/api/v1/agent/plan` and `/api/v1/agent/execute` endpoints. Natural language instructions are decomposed into execution DAGs through a three-tier parsing strategy:

1. **Regex pre-filter**: Handles single-step operations instantly at zero cost.
2. **Redis pattern cache**: Previously parsed instructions are cached. Repeat queries never hit the LLM.
3. **LLM API call**: Complex multi-step instructions use GPT-4o-mini (~$0.0001/request) with a structured JSON schema.

### Evolving for N Worker Job Types

As the system grows from 3 job types to N, the agentic layer needs to evolve:

#### 1. Dynamic Capability Registry

Instead of hardcoding job types in the LLM prompt, maintain a **capability registry** -- a database/config table describing each worker type:

```json
{
  "trim": {
    "description": "Trim video to a time range",
    "params": ["start_time", "end_time"],
    "input": "video",
    "output": "video"
  },
  "watermark": {
    "description": "Add image watermark overlay",
    "params": ["image_url", "position"],
    "input": "video",
    "output": "video"
  }
}
```

The LLM system prompt is dynamically generated from this registry. When a new worker type is deployed, it registers its capabilities, and the agent automatically knows about it.

#### 2. Constraint-Aware DAG Construction

Not all operations can be chained. The agent must understand input/output type compatibility:

- `transcode` outputs video, which can feed into `overlay` or `extract`.
- `extract` outputs audio, which cannot feed into `overlay` (needs video input).
- The LLM must respect these constraints. Enforce via post-validation: after LLM returns a DAG, validate that each step's input type matches its predecessor's output type.

#### 3. Cost-Aware Execution Planning

For a user instruction like "make this video ready for mobile: compress, add subtitles, and also give me an audio-only version", the optimal plan is a **diamond DAG**, not a linear chain:

```
           Input Video
           /         \
    Transcode       Extract Audio
         |               |
    Overlay Subs     Audio Output
         |
    Video Output
```

The LLM should identify parallelizable branches. This reduces total wall-clock time from sum(all steps) to max(parallel branches).

#### 4. Semantic Caching with Embeddings

At scale, exact-match caching (Tier 1) has limited hit rate. Upgrade to **semantic caching**:

1. Compute an embedding of the instruction using a cheap embedding model (e.g., `text-embedding-3-small`, ~$0.00002/request).
2. Search Redis (or a vector DB) for similar cached instructions above a cosine similarity threshold (e.g., 0.95).
3. If a match is found, reuse the cached DAG.

This means "compress this video" and "make this video smaller" return the same cached DAG without hitting the LLM.

#### 5. Cost Model Comparison

| Approach                     | Per-Request Cost | Latency  | Accuracy | Best For                         |
|-----------------------------|------------------|----------|----------|----------------------------------|
| Regex pre-filter            | $0               | <1ms     | 100%     | Known single-step operations     |
| Exact-match cache           | $0               | <5ms     | 100%     | Repeated identical instructions  |
| Semantic cache + embeddings | ~$0.00002        | ~50ms    | ~95%     | Paraphrased instructions         |
| LLM (GPT-4o-mini)          | ~$0.0001         | ~500ms   | ~95%     | Novel multi-step instructions    |
| LLM (GPT-4o)               | ~$0.003          | ~1000ms  | ~99%     | Ambiguous/complex instructions   |

The tiered approach means >80% of requests never reach the LLM. For a system handling 10,000 agent requests/hour, this saves ~$2.50/hour compared to calling GPT-4o for every request.

#### 6. Future: Autonomous Error Recovery

Today, if a pipeline step fails, the entire pipeline stops. A truly agentic system would:

1. Detect the failure and diagnose the cause (e.g., "subtitle file format not supported").
2. Attempt corrective action (e.g., convert SRT to ASS format, then retry).
3. If unrecoverable, notify the user with a clear explanation and suggested alternatives.

This requires a **planning-execution-observation loop** where the agent can re-plan based on runtime feedback -- essentially a ReAct pattern applied to media processing.

---

## Project Structure

```
backend/
├── docker-compose.yml          # Full stack: gateway, workers, redis, postgres, minio
├── Dockerfile.gateway          # Python 3.12 + FastAPI
├── Dockerfile.worker           # Python 3.12 + ffmpeg
├── requirements.txt            # Pinned Python dependencies
├── DESIGN.md                   # Architectural deep-dive
├── README.md                   # This file
├── .env.example                # Environment variable template
├── alembic.ini                 # Database migration config
├── alembic/                    # Migration scripts
├── gateway/                    # API Gateway service
│   ├── main.py                 # FastAPI app + lifespan hooks
│   ├── config.py               # pydantic-settings configuration
│   ├── db.py                   # Async SQLAlchemy session management
│   ├── api/v1/                 # Versioned API routes
│   │   ├── endpoints/jobs.py   # Job CRUD + file upload
│   │   ├── endpoints/workers.py # Worker pool health
│   │   ├── endpoints/agent.py  # Agentic orchestration endpoints
│   │   └── endpoints/sse.py    # Server-Sent Events for real-time status
│   ├── models/                 # SQLAlchemy ORM models
│   ├── schemas/                # Pydantic request/response schemas
│   └── services/               # Business logic layer
│       ├── job_service.py      # Job state machine
│       ├── queue_service.py    # Redis Stream operations
│       ├── storage_service.py  # MinIO file operations
│       ├── orchestrator.py     # Worker health + dead job recovery
│       └── agent_service.py    # LLM intent parser + DAG builder
├── worker/                     # Worker service
│   ├── main.py                 # Consumer loop + signal handling
│   ├── heartbeat.py            # Redis heartbeat publisher
│   └── processors/             # ffmpeg command builders
│       ├── overlay.py          # Subtitle burn-in
│       ├── transcode.py        # 480p downscale
│       └── extract.py          # Audio extraction to mp3
├── shared/                     # Code shared between gateway and worker
│   ├── constants.py            # Enums, Redis keys, config values
│   ├── redis_client.py         # Async Redis connection factory
│   └── storage_client.py       # Async S3/MinIO client factory
└── scripts/                    # Demo and utility scripts
    ├── demo_submit_overlay.py
    ├── demo_submit_transcode.py
    ├── demo_submit_extract.py
    └── demo_agent_query.py
```

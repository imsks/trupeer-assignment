from __future__ import annotations

import json
import re

import structlog

from gateway.config import get_settings
from gateway.schemas.agent import PipelineStep
from shared.constants import JobType
from shared.redis_client import get_redis

logger = structlog.get_logger()

PATTERN_CACHE_KEY = "agent:pattern_cache"

_DETERMINISTIC_PATTERNS: list[tuple[re.Pattern, list[dict]]] = [
    (
        re.compile(r"\b(add|burn)\s+(subtitle|srt|caption)", re.IGNORECASE),
        [{"step_index": 0, "job_type": JobType.OVERLAY, "params": {}}],
    ),
    (
        re.compile(r"\b(downscale|480p|lower\s+resolution|transcode|compress)", re.IGNORECASE),
        [{"step_index": 0, "job_type": JobType.TRANSCODE, "params": {}}],
    ),
    (
        re.compile(r"\b(extract\s+audio|strip\s+audio|audio\s+only|to\s+mp3|get\s+audio)", re.IGNORECASE),
        [{"step_index": 0, "job_type": JobType.EXTRACT, "params": {}}],
    ),
]

_LLM_SYSTEM_PROMPT = """You are a media processing pipeline planner. Given a user instruction about video processing, output a JSON array of pipeline steps.

Available job types:
- "overlay": Burn .srt subtitles into a video
- "transcode": Downscale video to 480p
- "extract": Extract audio from video as mp3

Each step must have:
- "step_index": integer starting from 0
- "job_type": one of "overlay", "transcode", "extract"
- "params": object with any extra parameters (can be empty {})
- "depends_on": null for first step, or the step_index it depends on

Output ONLY the JSON array, no explanation. Example:
[{"step_index": 0, "job_type": "transcode", "params": {}, "depends_on": null}, {"step_index": 1, "job_type": "overlay", "params": {}, "depends_on": 0}]"""


async def _try_regex_match(instruction: str) -> list[PipelineStep] | None:
    for pattern, steps_template in _DETERMINISTIC_PATTERNS:
        if pattern.search(instruction):
            return [PipelineStep(**s) for s in steps_template]
    return None


async def _try_cache(instruction: str) -> list[PipelineStep] | None:
    redis = await get_redis()
    normalized = instruction.strip().lower()
    cached = await redis.hget(PATTERN_CACHE_KEY, normalized)
    if cached:
        logger.info("agent_cache_hit", instruction=normalized)
        steps_data = json.loads(cached)
        return [PipelineStep(**s) for s in steps_data]
    return None


async def _cache_result(instruction: str, steps: list[PipelineStep]) -> None:
    redis = await get_redis()
    normalized = instruction.strip().lower()
    await redis.hset(
        PATTERN_CACHE_KEY,
        normalized,
        json.dumps([s.model_dump() for s in steps]),
    )


async def _call_llm(instruction: str) -> list[PipelineStep]:
    settings = get_settings()
    if not settings.openai_api_key or settings.openai_api_key.startswith("sk-your"):
        logger.warning("llm_api_key_not_configured")
        raise ValueError(
            "LLM API key not configured. Set OPENAI_API_KEY in .env. "
            "Falling back to regex parsing only."
        )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": _LLM_SYSTEM_PROMPT},
            {"role": "user", "content": instruction},
        ],
        temperature=0,
        max_tokens=512,
    )

    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    steps_data = json.loads(raw)
    steps = [PipelineStep(**s) for s in steps_data]

    valid_types = {t.value for t in JobType}
    for s in steps:
        if s.job_type not in valid_types:
            raise ValueError(f"LLM returned invalid job type: {s.job_type}")

    return steps


async def parse_instruction(instruction: str) -> list[PipelineStep]:
    """
    Three-tier intent parsing:
    1. Regex deterministic match (free, instant)
    2. Redis pattern cache (free, near-instant)
    3. LLM API call (costs ~$0.0001, ~500ms)
    """
    result = await _try_regex_match(instruction)
    if result:
        logger.info("agent_regex_match", instruction=instruction, steps=len(result))
        return result

    result = await _try_cache(instruction)
    if result:
        return result

    try:
        result = await _call_llm(instruction)
        await _cache_result(instruction, result)
        logger.info("agent_llm_parsed", instruction=instruction, steps=len(result))
        return result
    except ValueError:
        logger.warning("agent_llm_fallback_failed", instruction=instruction)
        return []
    except Exception:
        logger.exception("agent_llm_error", instruction=instruction)
        return []

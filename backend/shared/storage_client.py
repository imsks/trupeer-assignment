from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import aioboto3


def _s3_config() -> dict:
    return {
        "endpoint_url": f"http://{os.getenv('MINIO_ENDPOINT', 'localhost:9000')}",
        "aws_access_key_id": os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        "aws_secret_access_key": os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
        "region_name": "us-east-1",
    }


def get_bucket() -> str:
    return os.getenv("MINIO_BUCKET", "media-pipeline")


_session: aioboto3.Session | None = None


def _get_session() -> aioboto3.Session:
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


@asynccontextmanager
async def get_s3_client() -> AsyncGenerator:
    session = _get_session()
    async with session.client("s3", **_s3_config()) as client:
        yield client


async def ensure_bucket() -> None:
    """Create the media bucket if it doesn't exist."""
    async with get_s3_client() as s3:
        try:
            await s3.head_bucket(Bucket=get_bucket())
        except Exception:
            await s3.create_bucket(Bucket=get_bucket())

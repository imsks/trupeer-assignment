from __future__ import annotations

from typing import BinaryIO

import structlog

from shared.constants import MINIO_INPUT_PREFIX, MINIO_OUTPUT_PREFIX
from shared.storage_client import ensure_bucket, get_bucket, get_s3_client

logger = structlog.get_logger()


async def upload_input_file(
    job_id: str, file_obj: BinaryIO, filename: str
) -> str:
    await ensure_bucket()
    key = f"{MINIO_INPUT_PREFIX}/{job_id}/{filename}"
    async with get_s3_client() as s3:
        await s3.upload_fileobj(file_obj, get_bucket(), key)
    logger.info("file_uploaded", bucket=get_bucket(), key=key)
    return key


async def upload_subtitle_file(
    job_id: str, file_obj: BinaryIO, filename: str
) -> str:
    await ensure_bucket()
    key = f"{MINIO_INPUT_PREFIX}/{job_id}/{filename}"
    async with get_s3_client() as s3:
        await s3.upload_fileobj(file_obj, get_bucket(), key)
    logger.info("subtitle_uploaded", bucket=get_bucket(), key=key)
    return key


async def generate_presigned_download(key: str, expires_in: int = 3600) -> str:
    async with get_s3_client() as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": get_bucket(), "Key": key},
            ExpiresIn=expires_in,
        )
    return url


async def get_output_key(job_id: str) -> str | None:
    """List outputs for a job and return the first key found."""
    prefix = f"{MINIO_OUTPUT_PREFIX}/{job_id}/"
    async with get_s3_client() as s3:
        resp = await s3.list_objects_v2(Bucket=get_bucket(), Prefix=prefix, MaxKeys=1)
        contents = resp.get("Contents", [])
        if contents:
            return contents[0]["Key"]
    return None


async def download_file(key: str, local_path: str) -> None:
    async with get_s3_client() as s3:
        await s3.download_file(get_bucket(), key, local_path)


async def upload_output_file(key: str, local_path: str) -> None:
    await ensure_bucket()
    async with get_s3_client() as s3:
        await s3.upload_file(local_path, get_bucket(), key)
    logger.info("output_uploaded", bucket=get_bucket(), key=key)

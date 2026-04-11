# app/services/s3_service.py
"""
S3 upload service for voicemail audio files.
Uploads recorded audio blobs to the configured S3 bucket and returns
the object key and a permanent S3 URL for later retrieval.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import get_settings

logger = logging.getLogger(__name__)


def _get_client():
    """Return a boto3 S3 client using settings credentials."""
    s = get_settings()
    return boto3.client(
        "s3",
        region_name=s.AWS_REGION,
        aws_access_key_id=s.AWS_ACCESS_KEY_ID or None,
        aws_secret_access_key=s.AWS_SECRET_ACCESS_KEY or None,
    )


def upload_voicemail(
    audio_bytes: bytes,
    content_type: str = "audio/webm",
    ticket_ref: Optional[str] = None,
) -> dict:
    """
    Upload a voicemail audio blob to S3.

    Args:
        audio_bytes:  Raw audio bytes (webm / wav / mp3 etc.)
        content_type: MIME type of the audio (default: audio/webm)
        ticket_ref:   Optional reference string used in the S3 key path
                      (e.g. a temporary session ID or ticket number)

    Returns:
        {
            "s3_key":     "voicemails/2025-03-14/abc123.webm",
            "s3_url":     "https://<bucket>.s3.<region>.amazonaws.com/...",
            "size_bytes": 45231,
        }

    Raises:
        RuntimeError if the upload fails.
    """
    s = get_settings()

    # Build a unique, date-partitioned key
    date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    uid = uuid.uuid4().hex
    ext = _ext_for_content_type(content_type)
    ref_part = f"{ticket_ref}/" if ticket_ref else ""
    s3_key = f"voicemails/{date_prefix}/{ref_part}{uid}{ext}"

    try:
        client = _get_client()
        client.put_object(
            Bucket=s.S3_BUCKET_NAME,
            Key=s3_key,
            Body=audio_bytes,
            ContentType=content_type,
            Metadata={
                "uploaded-by": "arcella-support-platform",
                "ticket-ref": ticket_ref or "",
            },
        )
        s3_url = (
            f"https://{s.S3_BUCKET_NAME}.s3.{s.AWS_REGION}.amazonaws.com/{s3_key}"
        )
        logger.info(
            "Uploaded voicemail → s3://%s/%s (%d bytes)",
            s.S3_BUCKET_NAME, s3_key, len(audio_bytes),
        )
        return {
            "s3_key": s3_key,
            "s3_url": s3_url,
            "size_bytes": len(audio_bytes),
        }

    except (BotoCoreError, ClientError) as exc:
        logger.error("S3 upload failed: %s", exc)
        raise RuntimeError(f"S3 upload failed: {exc}") from exc


def _ext_for_content_type(content_type: str) -> str:
    mapping = {
        "audio/webm": ".webm",
        "audio/wav": ".wav",
        "audio/wave": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/ogg": ".ogg",
    }
    return mapping.get(content_type.lower().split(";")[0].strip(), ".webm")

# app/routers/transcribe.py
"""
POST /api/enquiry/transcribe
Receives a raw audio file upload, pushes it to S3, then sends it to
OpenAI Whisper-1 for transcription. Returns the transcript text plus
the S3 reference so the ticket can store where the voicemail lives.
"""
import logging
import tempfile
import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from openai import OpenAI

from app.config import get_settings
from app.services.s3_service import upload_voicemail

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enquiry", tags=["Enquiry"])

# Maximum audio size we'll accept: 24 MB (Whisper API hard limit is 25 MB)
MAX_AUDIO_BYTES = 24 * 1024 * 1024


@router.post("/transcribe")
async def transcribe_voicemail(
    audio: UploadFile = File(..., description="Recorded audio blob (.webm/.wav/.mp3)"),
    ticket_ref: str = Form(default="", description="Optional session / ticket reference"),
):
    """
    1. Receive the audio upload.
    2. Push to S3 (fire-and-forget; returns key + URL).
    3. Call OpenAI Whisper-1 for transcription.
    4. Return transcript + S3 metadata.
    """
    settings = get_settings()

    # ── Read & size-check ──────────────────────────────────────────────────
    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file received.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio exceeds the 24 MB limit ({len(audio_bytes) // 1024 // 1024} MB received).",
        )

    content_type = audio.content_type or "audio/webm"
    ref = ticket_ref.strip() or None

    # ── Upload to S3 ───────────────────────────────────────────────────────
    s3_result: dict = {}
    s3_error: str = ""
    try:
        s3_result = upload_voicemail(
            audio_bytes=audio_bytes,
            content_type=content_type,
            ticket_ref=ref,
        )
    except RuntimeError as exc:
        # S3 failure is non-fatal — log it, continue to transcription
        s3_error = str(exc)
        logger.warning("S3 upload skipped: %s", s3_error)

    # ── Transcribe via Whisper-1 ───────────────────────────────────────────
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured — transcription unavailable.",
        )

    # Whisper needs a real file on disk with a proper extension so the API
    # can infer the format. We write to a temp file, then stream it.
    ext = _ext_for_content_type(content_type)
    transcript_text = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        with open(tmp_path, "rb") as f:
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="text",
            )
        # response is a plain string when response_format="text"
        transcript_text = response if isinstance(response, str) else response.text

    except Exception as exc:
        logger.error("Whisper transcription failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Transcription failed: {exc}",
        )
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    return {
        "transcript": transcript_text.strip(),
        "s3_key":     s3_result.get("s3_key", ""),
        "s3_url":     s3_result.get("s3_url", ""),
        "size_bytes": s3_result.get("size_bytes", len(audio_bytes)),
        "s3_error":   s3_error,   # empty string = success
    }


def _ext_for_content_type(content_type: str) -> str:
    mapping = {
        "audio/webm": ".webm",
        "audio/wav":  ".wav",
        "audio/wave": ".wav",
        "audio/mpeg": ".mp3",
        "audio/mp4":  ".m4a",
        "audio/ogg":  ".ogg",
    }
    return mapping.get(content_type.lower().split(";")[0].strip(), ".webm")

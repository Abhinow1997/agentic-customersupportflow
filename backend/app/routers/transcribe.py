"""
POST /api/enquiry/transcribe
Receives a raw audio file upload and sends it to OpenAI Whisper-1 for
transcription. Returns the transcript text so the ticket can store the
captured voicemail content without any cloud storage dependency.
"""
from __future__ import annotations

import logging
import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enquiry", tags=["Enquiry"])

MAX_AUDIO_BYTES = 24 * 1024 * 1024


@router.post("/transcribe")
async def transcribe_voicemail(
    audio: UploadFile = File(..., description="Recorded audio blob (.webm/.wav/.mp3)"),
    ticket_ref: str = Form(default="", description="Optional session / ticket reference"),
):
    settings = get_settings()

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

    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured - transcription unavailable.",
        )

    ext = _ext_for_content_type(content_type)
    transcript_text = ""
    tmp_path = ""
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
        transcript_text = response if isinstance(response, str) else response.text
    except Exception as exc:
        logger.error("Whisper transcription failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Transcription failed: {exc}") from exc
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    return {
        "transcript": transcript_text.strip(),
        "ticket_ref": ref or "",
        "size_bytes": len(audio_bytes),
        "content_type": content_type,
    }


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

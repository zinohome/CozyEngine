"""Voice API Endpoints."""

from typing import Annotated

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.engines.registry import engine_registry
from app.core.config.manager import get_config
from app.observability.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.post("/audio/transcriptions")
async def transcribe_audio(
    file: Annotated[UploadFile, File()],
    model: Annotated[str | None, Form()] = None
):
    """Transcribe audio file."""
    config = get_config()
    stt_config = config.engines.voice.stt
    if not hasattr(config.engines, "voice") or not stt_config.enabled:
        raise HTTPException(status_code=503, detail="Voice features are disabled")

    provider = stt_config.default_provider
    provider_config = stt_config.providers.get(provider)
    if not provider_config:
        raise HTTPException(status_code=500, detail="STT Provider not configured")

    engine = await engine_registry.get_or_create_stt(
        provider, 
        {"model": model or provider_config.model, "timeout": provider_config.timeout}
    )
    
    if not engine:
        raise HTTPException(status_code=503, detail="STT Engine unavailable")

    try:
        text = await engine.transcribe(file.file, filename=file.filename or "audio.wav")
        return {"text": text}
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/audio/speech")
async def generate_speech(
    input: str,
    voice: str | None = None,
    stream: bool = False
):
    """Generate speech from text."""
    config = get_config()
    tts_config = config.engines.voice.tts
    if not hasattr(config.engines, "voice") or not tts_config.enabled:
        raise HTTPException(status_code=503, detail="Voice features are disabled")

    provider = tts_config.default_provider
    provider_config = tts_config.providers.get(provider)
    if not provider_config:
        raise HTTPException(status_code=500, detail="TTS Provider not configured")
        
    engine = await engine_registry.get_or_create_tts(
        provider,
        {
            "model": provider_config.model, 
            "voice": voice or provider_config.voice,
            "response_format": provider_config.response_format,
            "timeout": provider_config.timeout
        }
    )

    if not engine:
        raise HTTPException(status_code=503, detail="TTS Engine unavailable")

    try:
        if stream:
            return StreamingResponse(
                engine.generate_stream(input, voice=voice),
                media_type=f"audio/{provider_config.response_format}"
            )
        else:
            audio_content = await engine.generate(input, voice=voice)
            return Response(
                content=audio_content, 
                media_type=f"audio/{provider_config.response_format}"
            )
    except Exception as e:
        logger.error(f"Speech generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

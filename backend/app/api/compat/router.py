"""Compatibility API Router."""

from fastapi import APIRouter
from app.api.compat.sessions import router as sessions_router
from app.api.compat.personalities import router as personalities_router
from app.api.compat.tools import router as tools_router
from app.api.v1.voice import router as voice_router

router = APIRouter()

# CozyChat Compatible Enpdoints
# /v1/chat/sessions
router.include_router(sessions_router, prefix="/chat/sessions", tags=["Compat-Sessions"])

# /v1/personalities
router.include_router(personalities_router, prefix="/personalities", tags=["Compat-Personalities"])

# /v1/tools
router.include_router(tools_router, prefix="/tools", tags=["Compat-Tools"])

# /v1/audio (Aliases for voice features)
# The voice router already defines /audio/transcriptions and /audio/speech
# If we need exact /audio/stt key matching, we might need a dedicated wrapper.
# For now we assume the client can use the standard one or we add aliases here.

# Add simple aliases for CozyChat legacy paths if needed
# STT: /v1/audio/stt -> /v1/audio/transcriptions (Conceptually)
# TTS: /v1/audio/tts -> /v1/audio/speech (Conceptually)

# Since voice_router is locally imported, we can mount it or just specific endpoints
# But usually compat implies strict path matching.
# Let's add specific wrappers for stt/tts if strictly required.

@router.post("/audio/stt", tags=["Compat-Audio"])
async def compat_stt():
    """Compatibility endpoint for STT (Not implemented, use /v1/audio/transcriptions)."""
    return {"error": "Please use /v1/audio/transcriptions"}

@router.post("/audio/tts", tags=["Compat-Audio"])
async def compat_tts():
    """Compatibility endpoint for TTS (Not implemented, use /v1/audio/speech)."""
    return {"error": "Please use /v1/audio/speech"}

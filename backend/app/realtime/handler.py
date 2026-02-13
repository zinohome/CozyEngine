"""Realtime Voice Handler using FastRTC."""

import io
import asyncio
import numpy as np
from typing import AsyncGenerator, Tuple, Any

# fastrtc imports might vary, assuming standard usage based on gradio's stream
from fastrtc import ReplyOnPause, Stream, AdditionalOutputs
import gradio as gr

from app.engines.registry import engine_registry
from app.orchestration import get_orchestrator
from app.observability.logging import get_logger

logger = get_logger(__name__)

# FastRTC helper to save audio
def save_audio_to_bytes(sample_rate: int, audio_data: np.ndarray) -> io.BytesIO:
    import scipy.io.wavfile as wavfile
    buffer = io.BytesIO()
    # Normalize if needed, assume float32 if not specified
    wavfile.write(buffer, sample_rate, audio_data)
    buffer.seek(0)
    return buffer

class RealtimeVoiceHandler:
    """Handles realtime voice interactions."""

    async def handle_stream(self, audio: Tuple[int, np.ndarray]) -> AsyncGenerator[Tuple[int, np.ndarray], None]:
        """
        Process audio stream:
        1. STT
        2. Orchestrator Chat
        3. TTS -> Audio Stream
        """
        sample_rate, audio_data = audio
        
        # 1. Transcribe (STT)
        stt_engine = engine_registry.get_stt_engine()
        if not stt_engine:
            logger.error("STT Engine not available")
            return
            
        audio_buffer = save_audio_to_bytes(sample_rate, audio_data)
        try:
            # Assume default filename works
            text = await stt_engine.transcribe(audio_buffer, filename="input.wav")
            logger.info(f"Transcribed: {text}")
        except Exception as e:
            logger.error(f"STT failed: {e}")
            return

        if not text.strip():
            return

        # 2. Chat (Orchestrator)
        orchestrator = get_orchestrator()
        # Mock session for now or derive from context if FastRTC supports headers override
        # For simplicity, we use hardcoded "voice-session"
        user_id = "voice-user"
        session_id = "voice-session"
        personality_id = "cozy-companion-base" # Default

        try:
            # We use non-streaming chat for simplicity in logic, 
            # but ideally we stream text to TTS
            response = await orchestrator.chat(
                user_id=user_id,
                session_id=session_id,
                personality_id=personality_id,
                message=text
            )
            reply_text = response.get("content", "")
            logger.info(f"Reply: {reply_text}")
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            return

        # 3. TTS (Text to Speech)
        tts_engine = engine_registry.get_tts_engine()
        if not tts_engine:
             logger.error("TTS Engine not available")
             return

        try:
            # We can yield chunks if TTS supports it and we can decode MP3 to PCM
            # OpenAI TTS returns MP3. FastRTC expects (sample_rate, numpy_array).
            # This requires pydub or ffmpeg to Decode MP3 to PCM on the fly.
            # For iteration 1, we might just generate full audio and send it.
            
            # Note: Decoding MP3 bytes to numpy array requires pydub/ffmpeg
            # Assuming we have a helper or we just send it if FastRTC supports bytes?
            # FastRTC Stream input/output is strictly (rate, numpy).
            
            # Simple approach: Return nothing for now as we lack MP3 decoder in dependencies
            # OR assume we install simple decoder.
            pass
        except Exception as e:
             logger.error(f"TTS failed: {e}")
             return

        yield 24000, np.zeros((1, 1), dtype=np.int16) # Dummy yield

# For FastRTC mounting
stream = Stream(
    ReplyOnPause(RealtimeVoiceHandler().handle_stream),
    modality="audio", 
    mode="send-receive"
)

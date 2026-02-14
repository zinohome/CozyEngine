"""Realtime Voice Handler using FastRTC."""

import io
import asyncio
import numpy as np
import scipy.io.wavfile as wavfile
from typing import AsyncGenerator, Tuple, Any
from pydub import AudioSegment

from fastrtc import ReplyOnPause, Stream, AdditionalOutputs
import gradio as gr

from app.engines.registry import engine_registry
from app.orchestration import get_orchestrator
from app.observability.logging import get_logger

logger = get_logger(__name__)

class RealtimeVoiceHandler:
    """Handles realtime voice interactions."""

    async def handle_stream(self, audio: Tuple[int, np.ndarray], request: gr.Request = None) -> AsyncGenerator[Tuple[int, np.ndarray], None]:
        """
        Process audio stream:
        1. STT (Speech to Text)
        2. Orchestrator Chat
        3. TTS (Text to Speech) -> Audio Stream
        """
        if not audio:
            return

        # Determine User and Session from Request
        user_id = "realtime-user"
        session_id = "realtime-session"
        
        if request:
            # Use Gradio session_hash as session_id if available
            if hasattr(request, "session_hash"):
                session_id = f"rt-{request.session_hash}"
            
            # Use authenticated user if available (e.g. via HF_TOKEN or Basic Auth)
            if hasattr(request, "username") and request.username:
                user_id = request.username
            elif hasattr(request, "headers"):
                # Fallback to header inspection
                user_id = request.headers.get("x-user-id", user_id)
                session_id = request.headers.get("x-session-id", session_id)
        
        sample_rate, audio_data = audio
        
        # 1. Transcribe (STT)
        stt_engine = engine_registry.get_stt_engine()
        if not stt_engine:
            logger.error("STT Engine not available")
            return
            
        # Convert numpy array to WAV bytes for OpenAI
        audio_buffer = io.BytesIO()
        try:
            wavfile.write(audio_buffer, sample_rate, audio_data)
            audio_buffer.seek(0)
        except Exception as e:
            logger.error("Failed to convert audio to wav", error=str(e))
            return
        
        text = ""
        try:
            # We use a mocked filename to hint format to OpenAI if needed
            text = await stt_engine.transcribe(audio_buffer, filename="input.wav")
            logger.info("Transcribed audio", text=text)
        except Exception as e:
            logger.error("STT failed", error=str(e))
            return

        if not text or not text.strip():
            return

        # 2. Chat (Orchestrator)
        orchestrator = get_orchestrator()
        if not orchestrator:
            logger.error("Orchestrator not initialized")
            return

        personality_id = "cozy-companion-base"

        reply_text = ""
        try:
            response = await orchestrator.chat(
                user_id=user_id,
                session_id=session_id,
                personality_id=personality_id,
                message=text
            )
            reply_text = response.get("content", "")
            logger.info("Chat reply", reply_text=reply_text)
        except Exception as e:
            logger.error("Orchestration failed", error=str(e))
            return

        if not reply_text:
            return

        # 3. TTS (Text to Speech)
        tts_engine = engine_registry.get_tts_engine()
        if not tts_engine:
             logger.error("TTS Engine not available")
             return

        try:
            # Generate audio (MP3 by default from OpenAI)
            audio_bytes = await tts_engine.generate(reply_text)
            
            # Decode MP3/WAV to PCM using pydub
            # FastRTC expects (sample_rate, numpy_array)
            seg = AudioSegment.from_file(io.BytesIO(audio_bytes))
            
            # Convert to numpy array of samples
            # pydub stores as raw audio data, usually int16
            samples = np.array(seg.get_array_of_samples())
            
            # Handle channels
            if seg.channels == 2:
                samples = samples.reshape((-1, 2))
            
            yield (seg.frame_rate, samples)
            
        except Exception as e:
             logger.error("TTS processing failed", error=str(e))

# For FastRTC mounting
stream = Stream(
    ReplyOnPause(RealtimeVoiceHandler().handle_stream),
    modality="audio", 
    mode="send-receive",
    ui_args={"title": "CozyEngine Realtime Voice"}
)

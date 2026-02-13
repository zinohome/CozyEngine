"""Test Realtime Voice Handler."""

import sys
from unittest.mock import MagicMock, AsyncMock, patch
import numpy as np
import pytest

# Mock fastrtc and gradio before importing handler to avoid VAD model download/warmup
mock_fastrtc = MagicMock()
sys.modules["fastrtc"] = mock_fastrtc
sys.modules["gradio"] = MagicMock()

from app.realtime.handler import RealtimeVoiceHandler

@pytest.mark.asyncio
async def test_realtime_handler_flow():
    """Test full flow: Audio -> STT -> Orchestrator -> TTS -> Audio."""
    
    # Mock Engines
    mock_stt = AsyncMock()
    mock_stt.transcribe.return_value = "Hello AI"
    
    mock_tts = AsyncMock()
    # Mock TTS returning mp3 bytes (empty for simplicity, but valid for BytesIO)
    # We need valid mp3 or wav headers for pydub to not crash?
    # Or we mock AudioSegment.from_file
    mock_tts.generate.return_value = b"fake_audio_bytes"

    # Mock Orchestrator
    mock_orch = AsyncMock()
    mock_orch.chat.return_value = {"content": "Hello Human"}

    # Mock Engine Registry
    with patch("app.realtime.handler.engine_registry") as mock_registry:
        mock_registry.get_stt_engine.return_value = mock_stt
        mock_registry.get_tts_engine.return_value = mock_tts
        
        # Mock get_orchestrator
        with patch("app.realtime.handler.get_orchestrator") as mock_get_orch:
            mock_get_orch.return_value = mock_orch
            
            # Mock pydub AudioSegment to avoid real decoding of fake bytes
            with patch("app.realtime.handler.AudioSegment") as mock_segment_cls:
                mock_seg_instance = MagicMock()
                mock_seg_instance.get_array_of_samples.return_value = [0, 0, 0, 0] # Fake samples
                mock_seg_instance.frame_rate = 24000
                mock_seg_instance.channels = 1
                mock_segment_cls.from_file.return_value = mock_seg_instance
                
                # patch np.array to return mocked numpy array
                # Actually AudioSegment.get_array_of_samples returns standard list or array.array
                # np.array([0,0]) works.
                
                handler = RealtimeVoiceHandler()
                
                # Create fake input audio: (rate, numpy array)
                fake_audio = (24000, np.zeros((100,), dtype=np.int16))
                
                # Run handler
                gen = handler.handle_stream(fake_audio)
                
                results = []
                async for item in gen:
                    results.append(item)
                
                # Assertions
                mock_stt.transcribe.assert_awaited_once()
                mock_orch.chat.assert_awaited_once()
                mock_tts.generate.assert_awaited_once_with("Hello Human")
                
                # Check output
                assert len(results) == 1
                sample_rate, audio_data = results[0]
                assert sample_rate == 24000
                assert isinstance(audio_data, np.ndarray)


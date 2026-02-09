"""编排器测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.personalities.models import (
    Personality,
    PersonalityAI,
    PersonalityRegistry,
)
from app.engines.ai import ChatMessage, ChatResponse
from app.engines.registry import EngineRegistry
from app.core.exceptions import NotFoundError
from app.orchestration.chat import ChatOrchestrator


@pytest.fixture
def personality_registry():
    """Create a test personality registry"""
    registry = PersonalityRegistry()
    personality = Personality(
        id="default",
        name="Default Assistant",
        description="Default assistant",
        system_prompt="You are a helpful assistant.",
        ai=PersonalityAI(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
        ),
    )
    registry.register(personality)
    return registry


@pytest.fixture
def engine_registry():
    """Create a test engine registry"""
    return EngineRegistry()


@pytest.fixture
def orchestrator(personality_registry, engine_registry):
    """Create a test orchestrator"""
    return ChatOrchestrator(personality_registry, engine_registry)


class TestChatOrchestrator:
    """ChatOrchestrator 测试"""

    def test_orchestrator_creation(self, orchestrator):
        """Test creating orchestrator"""
        assert orchestrator is not None

    @pytest.mark.asyncio
    async def test_chat_with_nonexistent_personality(self, orchestrator):
        """Test chat with non-existent personality"""
        with pytest.raises(NotFoundError):
            await orchestrator.chat(
                user_id="user1",
                session_id="session1",
                personality_id="nonexistent",
                message="Hello",
            )

    @pytest.mark.asyncio
    async def test_chat_with_mock_engine(self, orchestrator):
        """Test chat with mocked engine"""
        # Mock the engine
        mock_engine = AsyncMock()
        mock_engine.supports_tools = False
        mock_engine.chat = AsyncMock(
            return_value=ChatResponse(
                content="Hello, how can I help?",
                finish_reason="stop",
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 8,
                    "total_tokens": 18,
                },
            )
        )

        orchestrator.engine_registry._engines["openai"] = mock_engine

        # Mock persistence and db_manager
        with patch.object(orchestrator, "_persist_message", new_callable=AsyncMock):
            with patch("app.orchestration.chat.db_manager") as mock_db:
                mock_session = AsyncMock()
                mock_db.session = MagicMock()
                mock_db.session.return_value.__aenter__.return_value = mock_session
                mock_db.session.return_value.__aexit__.return_value = None
                
                with patch("os.getenv", return_value="test-key"):
                    response = await orchestrator.chat(
                        user_id="user1",
                        session_id="session1",
                        personality_id="default",
                        message="Hello",
                    )

        assert response["object"] == "chat.completion"
        assert len(response["choices"]) == 1
        assert "test-key" is not None

    @pytest.mark.asyncio
    async def test_chat_stream_with_mock_engine(self, orchestrator):
        """Test chat stream with mocked engine"""
        # Mock the engine
        mock_engine = AsyncMock()
        mock_engine.supports_tools = False

        async def mock_stream(*args, **kwargs):
            yield {"content": "Hello", "finish_reason": None}
            yield {"content": ", ", "finish_reason": None}
            yield {"content": "world!", "finish_reason": "stop"}

        mock_engine.chat_stream = mock_stream

        orchestrator.engine_registry._engines["openai"] = mock_engine

        # Mock persistence and db_manager
        with patch.object(orchestrator, "_persist_message", new_callable=AsyncMock):
            with patch("app.orchestration.chat.db_manager") as mock_db:
                mock_session = AsyncMock()
                mock_db.session = MagicMock()
                mock_db.session.return_value.__aenter__.return_value = mock_session
                mock_db.session.return_value.__aexit__.return_value = None
                
                with patch("os.getenv", return_value="test-key"):
                    chunks = []
                    async for chunk in orchestrator.chat_stream(
                        user_id="user1",
                        session_id="session1",
                        personality_id="default",
                        message="Hello",
                    ):
                        chunks.append(chunk)

        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_get_api_key_openai(self, orchestrator):
        """Test getting OpenAI API key"""
        with patch("os.getenv", return_value="test-key"):
            key = orchestrator._get_api_key("openai")
            assert key == "test-key"

    @pytest.mark.asyncio
    async def test_get_api_key_unknown_engine(self, orchestrator):
        """Test getting API key for unknown engine"""
        with pytest.raises(ValueError, match="Unknown engine type"):
            orchestrator._get_api_key("unknown")


class TestOrchestratorInitialization:
    """编排器初始化测试"""

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test orchestrator initialization"""
        from app.orchestration.chat import initialize_orchestrator

        personality_registry = PersonalityRegistry()
        engine_registry = EngineRegistry()

        orchestrator = await initialize_orchestrator(personality_registry, engine_registry)
        assert orchestrator is not None

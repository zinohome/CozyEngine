"""AI 引擎测试"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.ai import AIEngine, ChatMessage, ChatResponse, OpenAIProvider
from app.engines.registry import EngineRegistry


class TestChatMessage:
    """ChatMessage 测试"""

    def test_chat_message_creation(self):
        """Test creating a ChatMessage"""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"


class TestChatResponse:
    """ChatResponse 测试"""

    def test_chat_response_creation(self):
        """Test creating a ChatResponse"""
        response = ChatResponse(content="Hello", finish_reason="stop")
        assert response.content == "Hello"
        assert response.finish_reason == "stop"


class TestOpenAIProvider:
    """OpenAI Provider 测试"""

    def test_provider_creation(self):
        """Test creating OpenAI provider"""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.api_key == "test-key"
        assert provider.base_url == "https://api.openai.com/v1"

    def test_provider_supports_tools(self):
        """Test that OpenAI provider supports tools"""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.supports_tools is True

    def test_provider_supports_vision(self):
        """Test that OpenAI provider supports vision"""
        provider = OpenAIProvider(api_key="test-key")
        assert provider.supports_vision is True

    @pytest.mark.asyncio
    async def test_provider_initialize(self):
        """Test provider initialization"""
        provider = OpenAIProvider(api_key="test-key")
        await provider.initialize()
        assert provider._initialized is True

    @pytest.mark.asyncio
    async def test_provider_health_check(self):
        """Test provider health check with mock"""
        provider = OpenAIProvider(api_key="test-key")
        await provider.initialize()

        # We can't easily test real health check without API key
        # This is a placeholder for actual testing with mocking


class TestEngineRegistry:
    """EngineRegistry 测试"""

    @pytest.mark.asyncio
    async def test_engine_registry_creation(self):
        """Test creating engine registry"""
        registry = EngineRegistry()
        assert registry._engines == {}

    @pytest.mark.asyncio
    async def test_engine_registry_missing_api_key(self):
        """Test engine creation with missing API key"""
        registry = EngineRegistry()
        with pytest.raises(ValueError, match="OpenAI API key is required"):
            registry._create_engine("openai", {})

    @pytest.mark.asyncio
    async def test_engine_registry_unknown_engine_type(self):
        """Test engine creation with unknown type"""
        registry = EngineRegistry()
        with pytest.raises(ValueError, match="Unknown engine type"):
            registry._create_engine("unknown", {})

    @pytest.mark.asyncio
    async def test_close_all_engines(self):
        """Test closing all engines"""
        registry = EngineRegistry()
        # Create a mock engine
        mock_engine = AsyncMock(spec=AIEngine)
        registry._engines["test"] = mock_engine

        await registry.close_all()
        mock_engine.close.assert_called_once()
        assert len(registry._engines) == 0

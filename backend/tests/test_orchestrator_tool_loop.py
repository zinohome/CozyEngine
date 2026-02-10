"""Orchestrator Tool Loop Integration Tests

测试编排器工具调用循环的完整流程：
1. AI engine 返回 tool_calls
2. 执行工具
3. 回填结果到消息
4. 继续调用 AI engine
5. 验证整个流程
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.engines.ai import AIEngine, ChatMessage, ChatResponse
from app.engines.registry import EngineRegistry
from app.engines.tools.basic import BasicToolsEngine
from app.core.personalities import PersonalityRegistry, Personality
from app.core.personalities.models import PersonalityAI, PersonalityTools, PersonalityMemory
from app.orchestration.chat import ChatOrchestrator


class MockAIEngine(AIEngine):
    """Mock AI Engine for testing"""

    def __init__(self, responses: list[ChatResponse]):
        self.responses = responses
        self.call_count = 0

    @property
    def supports_tools(self) -> bool:
        return True

    async def initialize(self):
        pass

    async def health_check(self) -> bool:
        return True

    async def close(self):
        pass

    async def chat(
        self,
        messages: list,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResponse:
        """返回预设的response，模拟tool_calls"""
        if self.call_count < len(self.responses):
            response = self.responses[self.call_count]
            self.call_count += 1
            return response
        # 默认返回stop
        return ChatResponse(content="Default response", finish_reason="stop")

    async def chat_stream(self, messages, temperature=None, max_tokens=None, top_p=None, tools=None):
        """Streaming not tested in this integration test"""
        raise NotImplementedError


@pytest.fixture
def mock_personality():
    """创建测试用personality"""
    return Personality(
        id="test_personality",
        name="Test Personality",
        description="Test",
        system_prompt="You are a test assistant.",
        ai=PersonalityAI(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=2000,
            top_p=1.0,
        ),
        tools=PersonalityTools(enabled=True, allowed_tools=["get_current_time", "calculate"]),
        memory=PersonalityMemory(enabled=False),
        metadata={},
    )


@pytest.fixture
def personality_registry(mock_personality):
    """创建包含测试personality的registry"""
    registry = PersonalityRegistry()
    registry.register(mock_personality)
    return registry


@pytest.fixture
async def tools_engine():
    """创建并初始化tools engine"""
    engine = BasicToolsEngine()
    await engine.initialize()
    return engine


@pytest.mark.asyncio
async def test_tool_loop_single_iteration(personality_registry, tools_engine):
    """测试单次工具调用循环"""

    # 模拟AI响应：第一次返回tool_calls，第二次返回final answer
    mock_responses = [
        # 第一次：AI要求调用get_current_time工具
        ChatResponse(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_123",
                    "function": {"name": "get_current_time", "arguments": '{"format": "iso"}'},
                }
            ],
        ),
        # 第二次：AI根据工具结果生成最终答案
        ChatResponse(
            content="The current time is 2026-02-10T10:00:00",
            finish_reason="stop",
        ),
    ]

    # 创建mock engine和registry
    mock_engine = MockAIEngine(mock_responses)
    engine_registry = EngineRegistry()
    engine_registry._engines["test"] = mock_engine

    # 创建orchestrator
    orchestrator = ChatOrchestrator(
        personality_registry=personality_registry,
        engine_registry=engine_registry,
    )
    orchestrator.tools_engine = tools_engine

    # 执行chat（会触发工具循环）
    with patch.object(orchestrator, "_get_api_key", return_value="test_key"):
        with patch.object(orchestrator, "_get_base_url", return_value="https://test.com"):
            with patch("app.storage.database.db_manager.session") as mock_session:
                mock_session.return_value.__aenter__.return_value = AsyncMock()
                with patch("app.services.audit.AuditService.log_tool_invocation", new=AsyncMock()):
                    # Mock engine_registry.get_or_create to return our mock engine
                    async def mock_get_or_create(engine_type, config):
                        return mock_engine

                    engine_registry.get_or_create = mock_get_or_create

                    result = await orchestrator.chat(
                        user_id="test_user",
                        session_id="test_session",
                        personality_id="test_personality",
                        message="What time is it?",
                    )

    # 验证
    assert result["choices"][0]["message"]["content"] == "The current time is 2026-02-10T10:00:00"
    assert mock_engine.call_count == 2  # 调用了两次AI engine
    assert result["choices"][0]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_tool_loop_multiple_iterations(personality_registry, tools_engine):
    """测试多次工具调用循环"""

    mock_responses = [
        # 第一次：调用get_current_time
        ChatResponse(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_1",
                    "function": {"name": "get_current_time", "arguments": '{"format": "iso"}'},
                }
            ],
        ),
        # 第二次：调用calculate
        ChatResponse(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_2",
                    "function": {"name": "calculate", "arguments": '{"expression": "2 + 2"}'},
                }
            ],
        ),
        # 第三次：最终答案
        ChatResponse(
            content="The time is 2026-02-10 and 2+2=4",
            finish_reason="stop",
        ),
    ]

    mock_engine = MockAIEngine(mock_responses)
    engine_registry = EngineRegistry()
    engine_registry._engines["test"] = mock_engine

    orchestrator = ChatOrchestrator(
        personality_registry=personality_registry,
        engine_registry=engine_registry,
    )
    orchestrator.tools_engine = tools_engine

    with patch.object(orchestrator, "_get_api_key", return_value="test_key"):
        with patch.object(orchestrator, "_get_base_url", return_value="https://test.com"):
            with patch("app.storage.database.db_manager.session") as mock_session:
                mock_session.return_value.__aenter__.return_value = AsyncMock()
                with patch("app.services.audit.AuditService.log_tool_invocation", new=AsyncMock()):
                    async def mock_get_or_create(engine_type, config):
                        return mock_engine

                engine_registry.get_or_create = mock_get_or_create

                result = await orchestrator.chat(
                    user_id="test_user",
                    session_id="test_session",
                    personality_id="test_personality",
                    message="Test multiple tools",
                )

    # 验证多次迭代
    assert mock_engine.call_count == 3
    assert "2+2=4" in result["choices"][0]["message"]["content"]
    assert result["choices"][0]["finish_reason"] == "stop"


@pytest.mark.asyncio
async def test_tool_loop_iteration_limit(personality_registry, tools_engine):
    """测试工具循环迭代次数限制（max 10）"""

    # 创建11次tool_calls响应（超过限制）
    mock_responses = []
    for i in range(12):
        mock_responses.append(
            ChatResponse(
                content="",
                finish_reason="tool_calls",
                tool_calls=[
                    {
                        "id": f"call_{i}",
                        "function": {"name": "get_current_time", "arguments": '{"format": "iso"}'},
                    }
                ],
            )
        )

    mock_engine = MockAIEngine(mock_responses)
    engine_registry = EngineRegistry()

    orchestrator = ChatOrchestrator(
        personality_registry=personality_registry,
        engine_registry=engine_registry,
    )
    orchestrator.tools_engine = tools_engine
    orchestrator.max_tool_iterations = 10

    with patch.object(orchestrator, "_get_api_key", return_value="test_key"):
        with patch.object(orchestrator, "_get_base_url", return_value="https://test.com"):
            with patch("app.storage.database.db_manager.session") as mock_session:
                mock_session.return_value.__aenter__.return_value = AsyncMock()
                with patch("app.services.audit.AuditService.log_tool_invocation", new=AsyncMock()):
                    async def mock_get_or_create(engine_type, config):
                        return mock_engine

                engine_registry.get_or_create = mock_get_or_create

                result = await orchestrator.chat(
                    user_id="test_user",
                    session_id="test_session",
                    personality_id="test_personality",
                    message="Test iteration limit",
                )

    # 验证：应该在10次迭代后停止
    assert mock_engine.call_count == 10  # 正好10次（迭代限制）
    # 结果应该是最后一次的内容（虽然finish_reason是tool_calls）
    assert result["choices"][0]["finish_reason"] == "tool_calls"


@pytest.mark.asyncio
async def test_tool_execution_failure(personality_registry, tools_engine):
    """测试工具执行失败的情况"""

    mock_responses = [
        # AI要求调用一个不存在的工具
        ChatResponse(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_fail",
                    "function": {"name": "nonexistent_tool", "arguments": "{}"},
                }
            ],
        ),
        # AI根据错误信息生成响应
        ChatResponse(
            content="I couldn't execute that tool",
            finish_reason="stop",
        ),
    ]

    mock_engine = MockAIEngine(mock_responses)
    engine_registry = EngineRegistry()

    orchestrator = ChatOrchestrator(
        personality_registry=personality_registry,
        engine_registry=engine_registry,
    )
    orchestrator.tools_engine = tools_engine

    with patch.object(orchestrator, "_get_api_key", return_value="test_key"):
        with patch.object(orchestrator, "_get_base_url", return_value="https://test.com"):
            with patch("app.storage.database.db_manager.session") as mock_session:
                mock_session.return_value.__aenter__.return_value = AsyncMock()
                with patch("app.services.audit.AuditService.log_tool_invocation", new=AsyncMock()):
                    async def mock_get_or_create(engine_type, config):
                        return mock_engine

                engine_registry.get_or_create = mock_get_or_create

                result = await orchestrator.chat(
                    user_id="test_user",
                    session_id="test_session",
                    personality_id="test_personality",
                    message="Test tool failure",
                )

    # 验证：即使工具失败，流程应该继续
    assert mock_engine.call_count == 2
    assert "couldn't execute" in result["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_permission_denied_tool(personality_registry, tools_engine):
    """测试工具权限被拒绝的情况"""

    # 创建一个不允许工具的personality
    restricted_personality = Personality(
        id="restricted",
        name="Restricted",
        description="No tools allowed",
        system_prompt="You are restricted.",
        ai=PersonalityAI(
            provider="openai",
            model="gpt-4",
            temperature=0.7,
            max_tokens=2000,
            top_p=1.0,
        ),
        tools=PersonalityTools(enabled=True, allowed_tools=[]),  # 空列表，不允许任何工具
        memory=PersonalityMemory(enabled=False),
        metadata={},
    )

    personality_registry.register(restricted_personality)

    mock_responses = [
        # AI尝试调用工具
        ChatResponse(
            content="",
            finish_reason="tool_calls",
            tool_calls=[
                {
                    "id": "call_denied",
                    "function": {"name": "get_current_time", "arguments": '{"format": "iso"}'},
                }
            ],
        ),
        # AI得到权限拒绝错误后的响应
        ChatResponse(
            content="I don't have permission to check the time",
            finish_reason="stop",
        ),
    ]

    mock_engine = MockAIEngine(mock_responses)
    engine_registry = EngineRegistry()

    orchestrator = ChatOrchestrator(
        personality_registry=personality_registry,
        engine_registry=engine_registry,
    )
    orchestrator.tools_engine = tools_engine

    with patch.object(orchestrator, "_get_api_key", return_value="test_key"):
        with patch.object(orchestrator, "_get_base_url", return_value="https://test.com"):
            with patch("app.storage.database.db_manager.session") as mock_session:
                mock_session.return_value.__aenter__.return_value = AsyncMock()
                with patch("app.services.audit.AuditService.log_tool_invocation", new=AsyncMock()):
                    async def mock_get_or_create(engine_type, config):
                        return mock_engine

                engine_registry.get_or_create = mock_get_or_create

                result = await orchestrator.chat(
                    user_id="test_user",
                    session_id="test_session",
                    personality_id="restricted",
                    message="What time is it?",
                )

    # 验证：权限拒绝不会中断流程
    assert mock_engine.call_count == 2
    assert "permission" in result["choices"][0]["message"]["content"].lower()

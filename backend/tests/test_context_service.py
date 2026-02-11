"""ContextService tests."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.context.service import ContextService
from app.core.personalities.models import Personality, PersonalityAI, PersonalityMemory
from app.engines.ai import ChatMessage
from app.engines.chat_memory import MemoryItem, ChatMemoryEngine
from app.engines.knowledge import KnowledgeItem, KnowledgeEngine
from app.engines.registry import EngineRegistry
from app.engines.user_profile import UserProfileEngine, UserProfileResult


class StubKnowledgeEngine(KnowledgeEngine):
    async def initialize(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def search_knowledge(self, query, dataset_names=None, top_k=5):
        return [KnowledgeItem(content="Knowledge content", source="stub")]

    async def add_knowledge(self, content, dataset_name=None, metadata=None):
        return "kid-1"


class StubUserProfileEngine(UserProfileEngine):
    async def initialize(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def get_profile(self, user_id: str, max_token_size: int) -> UserProfileResult:
        return UserProfileResult(profile_text="Profile text", token_size=3)

    async def update_profile(self, user_id: str, messages: list[dict]) -> bool:
        return True


class StubChatMemoryEngine(ChatMemoryEngine):
    async def initialize(self) -> None:
        return None

    async def health_check(self) -> bool:
        return True

    async def close(self) -> None:
        return None

    async def search_memories(self, query, user_id, session_id, top_k=5):
        return [MemoryItem(content="Memory content")]

    async def add_memory(self, user_id, session_id, messages):
        return ["mem-1"]


@pytest.fixture
def personality():
    return Personality(
        id="default",
        name="Default",
        description="Default assistant",
        system_prompt="You are helpful.",
        ai=PersonalityAI(provider="openai", model="gpt-4"),
        memory=PersonalityMemory(enabled=True, recall_top_k=3),
    )


def _build_dummy_config(
    *,
    max_context_tokens: int = 1000,
    reserve_for_completion: int = 100,
    personalization_budget: int = 100,
    include_knowledge: bool = True,
    include_user_profile: bool = True,
    include_chat_memory: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        context=SimpleNamespace(
            token_budget=SimpleNamespace(
                max_context_tokens=max_context_tokens,
                reserve_for_completion=reserve_for_completion,
                personalization_budget=personalization_budget,
            ),
            parallel_execution=SimpleNamespace(enabled=True, timeout=1.0),
            assembly=SimpleNamespace(
                include_system_prompt=True,
                include_knowledge=include_knowledge,
                include_user_profile=include_user_profile,
                include_chat_memory=include_chat_memory,
                include_tool_definitions=False,
            ),
            degradation=SimpleNamespace(enabled=True, allow_partial_failure=True, min_required_engines=0),
        ),
        engines=SimpleNamespace(
            knowledge=SimpleNamespace(
                enabled=include_knowledge,
                default_provider="cognee",
                providers={"cognee": SimpleNamespace(timeout=1.0)},
            ),
            user_profile=SimpleNamespace(
                enabled=include_user_profile,
                default_provider="local",
                timeout=1.0,
            ),
            chat_memory=SimpleNamespace(
                enabled=include_chat_memory,
                default_provider="mem0",
                providers={"mem0": SimpleNamespace(timeout=1.0)},
            ),
        ),
    )


@pytest.mark.asyncio
async def test_context_bundle_builds_and_messages(personality, monkeypatch):
    engine_registry = EngineRegistry()
    service = ContextService(engine_registry, config=_build_dummy_config())

    # Create stub engines and initialize them
    stub_knowledge = StubKnowledgeEngine()
    stub_profile = StubUserProfileEngine()
    stub_memory = StubChatMemoryEngine()
    await stub_knowledge.initialize()
    await stub_profile.initialize()
    await stub_memory.initialize()
    
    # Pre-populate engine registry caches to bypass get_or_create logic
    engine_registry._knowledge_engines["cognee"] = stub_knowledge
    engine_registry._user_profile_engines["local"] = stub_profile
    engine_registry._chat_memory_engines["mem0"] = stub_memory
    
    # Also set up locks to avoid issues
    engine_registry._knowledge_locks["cognee"] = asyncio.Lock()
    engine_registry._user_profile_locks["local"] = asyncio.Lock()
    engine_registry._chat_memory_locks["mem0"] = asyncio.Lock()
    
    monkeypatch.setattr(service, "_fetch_recent_messages", AsyncMock(return_value=[]))

    bundle = await service.build_context_bundle(
        user_id="user-1",
        session_id="not-a-uuid",
        current_message="Hello",
        personality=personality,
        max_tokens=None,  # Use config defaults instead of overriding
        request_id="req-1",
    )

    # Debug output removed
    assert bundle.user_profile is not None
    assert bundle.user_profile.profile_text == "Profile text"
    assert bundle.retrieved_knowledge
    assert bundle.retrieved_memories
    assert bundle.metadata["engines"]["knowledge"]["status"] == "ok"

    messages = service.to_messages(bundle, "Hello")
    assert messages[-1].role == "user"
    assert messages[-1].content == "Hello"


@pytest.mark.asyncio
async def test_context_bundle_truncates_recent_messages(personality, monkeypatch):
    engine_registry = EngineRegistry()
    service = ContextService(
        engine_registry,
        config=_build_dummy_config(
            max_context_tokens=20,
            reserve_for_completion=5,
            personalization_budget=5,
            include_knowledge=False,
            include_user_profile=False,
            include_chat_memory=False,
        ),
    )
    monkeypatch.setattr(
        service,
        "_fetch_recent_messages",
        AsyncMock(
            return_value=[
                ChatMessage(role="user", content="A" * 200),
                ChatMessage(role="assistant", content="Short reply"),
            ]
        ),
    )

    bundle = await service.build_context_bundle(
        user_id="user-1",
        session_id="not-a-uuid",
        current_message="Hello",
        personality=personality,
        max_tokens=5,
        request_id="req-2",
    )

    assert len(bundle.recent_messages) == 1
    assert bundle.recent_messages[0].content == "Short reply"
    assert bundle.token_budget.truncated is True

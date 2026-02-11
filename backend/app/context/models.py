"""Context models for the context layer."""

from dataclasses import dataclass, field
from typing import Any

from app.engines.ai import ChatMessage
from app.engines.chat_memory import MemoryItem
from app.engines.knowledge import KnowledgeItem
from app.engines.user_profile import UserProfileResult


@dataclass
class TokenBudget:
    """Token budget bookkeeping for context assembly."""

    max_context_tokens: int
    reserve_for_completion: int
    available_context_tokens: int
    used_tokens: int
    truncated: bool
    sections: dict[str, int] = field(default_factory=dict)
    dropped_sections: list[str] = field(default_factory=list)


@dataclass
class ContextBundle:
    """Context bundle output for the orchestration layer."""

    system_prompts: list[str]
    recent_messages: list[ChatMessage]
    summarized_history: list[str]
    retrieved_knowledge: list[KnowledgeItem]
    retrieved_memories: list[MemoryItem]
    user_profile: UserProfileResult | None
    token_budget: TokenBudget
    metadata: dict[str, Any] = field(default_factory=dict)

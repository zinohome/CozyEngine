"""Context service for assembling personalized context."""

import asyncio
import time
import uuid

from sqlalchemy import select

from app.context.message_builder import context_to_messages
from app.context.models import ContextBundle, TokenBudget
from app.core.config.manager import get_config
from app.core.personalities.models import Personality
from app.engines.ai import ChatMessage
from app.engines.chat_memory import MemoryItem
from app.engines.knowledge import KnowledgeItem
from app.engines.registry import EngineRegistry
from app.engines.user_profile import UserProfileResult
from app.observability.logging import get_logger
from app.storage.database import db_manager
from app.storage.models import Message

logger = get_logger(__name__)


class ContextService:
    """Context service for building ContextBundle."""

    def __init__(self, engine_registry: EngineRegistry, config=None):
        self.engine_registry = engine_registry
        self._config = config

    async def build_context_bundle(
        self,
        user_id: str,
        session_id: str,
        current_message: str,
        personality: Personality,
        max_tokens: int | None = None,
        request_id: str | None = None,
    ) -> ContextBundle:
        """Build a context bundle for the current request."""
        config = self._get_config()
        context_cfg = config.context
        engines_cfg = config.engines
        request_id = request_id or str(uuid.uuid4())

        system_prompts = []
        if context_cfg.assembly.include_system_prompt:
            system_prompts.append(personality.system_prompt)

        recent_messages = await self._fetch_recent_messages(
            session_id=session_id,
            limit=20,
            request_id=request_id,
        )

        summary: list[str] = []

        knowledge_enabled = (
            context_cfg.assembly.include_knowledge and engines_cfg.knowledge.enabled
        )
        user_profile_enabled = (
            context_cfg.assembly.include_user_profile and engines_cfg.user_profile.enabled
        )
        chat_memory_enabled = (
            context_cfg.assembly.include_chat_memory
            and engines_cfg.chat_memory.enabled
            and personality.memory.enabled
        )

        engine_tasks = []
        engine_names = []
        if knowledge_enabled:
            engine_tasks.append(
                self._call_knowledge_engine(
                    current_message,
                    engines_cfg.knowledge.default_provider,
                    engines_cfg.knowledge.providers.get(
                        engines_cfg.knowledge.default_provider
                    ),
                    context_cfg.parallel_execution.timeout,
                    request_id,
                )
            )
            engine_names.append("knowledge")
        if user_profile_enabled:
            engine_tasks.append(
                self._call_user_profile_engine(
                    user_id,
                    engines_cfg.user_profile.default_provider,
                    engines_cfg.user_profile.timeout,
                    context_cfg.parallel_execution.timeout,
                    request_id,
                )
            )
            engine_names.append("user_profile")
        if chat_memory_enabled:
            engine_tasks.append(
                self._call_chat_memory_engine(
                    current_message,
                    user_id,
                    session_id,
                    personality.memory.recall_top_k,
                    engines_cfg.chat_memory.default_provider,
                    engines_cfg.chat_memory.providers.get(
                        engines_cfg.chat_memory.default_provider
                    ),
                    context_cfg.parallel_execution.timeout,
                    request_id,
                )
            )
            engine_names.append("chat_memory")

        knowledge_results: list[KnowledgeItem] = []
        user_profile_result: UserProfileResult | None = None
        memory_results: list[MemoryItem] = []
        metadata = {"engines": {}}

        if engine_tasks:
            if context_cfg.parallel_execution.enabled:
                results = await asyncio.gather(*engine_tasks)
            else:
                results = []
                for task in engine_tasks:
                    results.append(await task)

            for engine_name, (engine_data, engine_meta) in zip(engine_names, results):
                metadata["engines"][engine_name] = engine_meta
                if engine_name == "knowledge":
                    knowledge_results = engine_data
                elif engine_name == "user_profile":
                    user_profile_result = engine_data
                elif engine_name == "chat_memory":
                    memory_results = engine_data
        if "knowledge" not in metadata["engines"]:
            metadata["engines"]["knowledge"] = {
                "status": "skipped",
                "latency_ms": 0,
                "reason": "disabled",
                "cache_hit": False,
            }
        if "user_profile" not in metadata["engines"]:
            metadata["engines"]["user_profile"] = {
                "status": "skipped",
                "latency_ms": 0,
                "reason": "disabled",
                "cache_hit": False,
            }
        if "chat_memory" not in metadata["engines"]:
            metadata["engines"]["chat_memory"] = {
                "status": "skipped",
                "latency_ms": 0,
                "reason": "disabled",
                "cache_hit": False,
            }

        bundle = ContextBundle(
            system_prompts=system_prompts,
            recent_messages=recent_messages,
            summarized_history=summary,
            retrieved_knowledge=knowledge_results,
            retrieved_memories=memory_results,
            user_profile=user_profile_result,
            token_budget=self._apply_token_budget(
                system_prompts,
                recent_messages,
                summary,
                knowledge_results,
                memory_results,
                user_profile_result,
                max_tokens,
            ),
            metadata=metadata,
        )

        return bundle

    def to_messages(self, bundle: ContextBundle, current_message: str) -> list[ChatMessage]:
        """Convert ContextBundle into AI engine messages."""
        return context_to_messages(bundle, current_message)

    async def _call_knowledge_engine(
        self,
        query: str,
        provider: str,
        provider_config,
        timeout: float,
        request_id: str,
    ) -> tuple[list[KnowledgeItem], dict]:
        engine_timeout = provider_config.timeout if provider_config else timeout
        start_time = time.time()
        try:
            engine = await self.engine_registry.get_or_create_knowledge(
                provider, {"provider": provider}
            )
            results = await asyncio.wait_for(
                engine.search_knowledge(query=query, dataset_names=None, top_k=5),
                timeout=engine_timeout,
            )
            return results, self._build_engine_meta("ok", start_time, None, False)
        except asyncio.TimeoutError:
            logger.warning(
                "Knowledge engine timeout",
                request_id=request_id,
                provider=provider,
            )
            return [], self._build_engine_meta("degraded", start_time, "timeout", False)
        except Exception as e:
            logger.warning(
                "Knowledge engine failed",
                request_id=request_id,
                provider=provider,
                error=str(e),
            )
            return [], self._build_engine_meta("degraded", start_time, "error", False)

    async def _call_user_profile_engine(
        self,
        user_id: str,
        provider: str,
        provider_timeout: float,
        default_timeout: float,
        request_id: str,
    ) -> tuple[UserProfileResult, dict]:
        engine_timeout = provider_timeout or default_timeout
        start_time = time.time()
        try:
            engine = await self.engine_registry.get_or_create_user_profile(
                provider, {"provider": provider}
            )
            config = self._get_config()
            result = await asyncio.wait_for(
                engine.get_profile(
                    user_id=user_id,
                    max_token_size=config.context.token_budget.personalization_budget,
                ),
                timeout=engine_timeout,
            )
            return result, self._build_engine_meta("ok", start_time, None, False)
        except asyncio.TimeoutError:
            logger.warning(
                "User profile engine timeout",
                request_id=request_id,
                provider=provider,
            )
            return (
                UserProfileResult(profile_text="", token_size=0, metadata={}),
                self._build_engine_meta("degraded", start_time, "timeout", False),
            )
        except Exception as e:
            logger.warning(
                "User profile engine failed",
                request_id=request_id,
                provider=provider,
                error=str(e),
            )
            return (
                UserProfileResult(profile_text="", token_size=0, metadata={}),
                self._build_engine_meta("degraded", start_time, "error", False),
            )

    async def _call_chat_memory_engine(
        self,
        query: str,
        user_id: str,
        session_id: str,
        top_k: int,
        provider: str,
        provider_config,
        timeout: float,
        request_id: str,
    ) -> tuple[list[MemoryItem], dict]:
        engine_timeout = provider_config.timeout if provider_config else timeout
        start_time = time.time()
        try:
            engine = await self.engine_registry.get_or_create_chat_memory(
                provider, {"provider": provider}
            )
            results = await asyncio.wait_for(
                engine.search_memories(
                    query=query,
                    user_id=user_id,
                    session_id=session_id,
                    top_k=top_k,
                ),
                timeout=engine_timeout,
            )
            return results, self._build_engine_meta("ok", start_time, None, False)
        except asyncio.TimeoutError:
            logger.warning(
                "Chat memory engine timeout",
                request_id=request_id,
                provider=provider,
            )
            return [], self._build_engine_meta("degraded", start_time, "timeout", False)
        except Exception as e:
            logger.warning(
                "Chat memory engine failed",
                request_id=request_id,
                provider=provider,
                error=str(e),
            )
            return [], self._build_engine_meta("degraded", start_time, "error", False)

    @staticmethod
    def _build_engine_meta(status: str, start_time: float, reason: str | None, cache_hit: bool) -> dict:
        return {
            "status": status,
            "latency_ms": int((time.time() - start_time) * 1000),
            "reason": reason,
            "cache_hit": cache_hit,
        }

    async def _fetch_recent_messages(
        self,
        session_id: str,
        limit: int,
        request_id: str,
    ) -> list[ChatMessage]:
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            session_uuid = uuid.uuid5(uuid.NAMESPACE_URL, session_id)
            logger.info(
                "Normalized non-UUID session_id for recent message lookup",
                request_id=request_id,
                session_id=session_id,
                normalized_session_id=str(session_uuid),
            )

        async with db_manager.session() as session:
            result = await session.execute(
                select(Message)
                .where(Message.session_id == session_uuid)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            records = list(result.scalars())

        records.reverse()
        messages = [
            ChatMessage(role=record.role, content=record.content) for record in records
        ]
        return messages

    def _apply_token_budget(
        self,
        system_prompts: list[str],
        recent_messages: list[ChatMessage],
        summary: list[str],
        knowledge_items: list[KnowledgeItem],
        memory_items: list[MemoryItem],
        user_profile: UserProfileResult | None,
        max_tokens: int | None,
    ) -> TokenBudget:
        config = self._get_config()
        budget_cfg = config.context.token_budget
        reserve_for_completion = max_tokens or budget_cfg.reserve_for_completion
        max_context_tokens = budget_cfg.max_context_tokens
        available_context_tokens = max(0, max_context_tokens - reserve_for_completion)

        system_tokens = sum(_estimate_tokens(text) for text in system_prompts)
        recent_tokens = sum(_estimate_tokens(msg.content) for msg in recent_messages)
        summary_tokens = sum(_estimate_tokens(text) for text in summary)
        knowledge_tokens = sum(_estimate_tokens(item.content) for item in knowledge_items)
        memory_tokens = sum(_estimate_tokens(item.content) for item in memory_items)
        profile_tokens = _estimate_tokens(user_profile.profile_text) if user_profile else 0

        used_tokens = (
            system_tokens
            + recent_tokens
            + summary_tokens
            + knowledge_tokens
            + memory_tokens
            + profile_tokens
        )

        truncated = False
        dropped_sections: list[str] = []

        if system_tokens > available_context_tokens:
            truncated = True
            dropped_sections.extend(["recent_messages", "summary", "knowledge", "memories", "profile"])
            recent_messages.clear()
            summary.clear()
            knowledge_items.clear()
            memory_items.clear()
            if user_profile:
                user_profile.profile_text = ""
            return TokenBudget(
                max_context_tokens=max_context_tokens,
                reserve_for_completion=reserve_for_completion,
                available_context_tokens=available_context_tokens,
                used_tokens=system_tokens,
                truncated=True,
                sections={
                    "system": system_tokens,
                    "recent_messages": 0,
                    "summary": 0,
                    "knowledge": 0,
                    "memories": 0,
                    "profile": 0,
                },
                dropped_sections=dropped_sections,
            )

        remaining_tokens = available_context_tokens - system_tokens

        # Truncate recent messages (keep most recent that fit)
        original_recent_count = len(recent_messages)
        recent_messages[:] = _truncate_messages(recent_messages, remaining_tokens)
        recent_tokens = sum(_estimate_tokens(msg.content) for msg in recent_messages)
        remaining_tokens = max(0, remaining_tokens - recent_tokens)
        if len(recent_messages) < original_recent_count:
            truncated = True

        personalization_budget = min(budget_cfg.personalization_budget, remaining_tokens)

        # Truncate user profile
        profile_text = user_profile.profile_text if user_profile else ""
        original_profile_len = len(profile_text)
        profile_text = _truncate_text(profile_text, personalization_budget)
        profile_tokens = _estimate_tokens(profile_text)
        if user_profile:
            user_profile.profile_text = profile_text
        if len(profile_text) < original_profile_len:
            truncated = True
        personalization_budget = max(0, personalization_budget - profile_tokens)

        # Truncate knowledge items
        original_knowledge_count = len(knowledge_items)
        knowledge_items[:] = _truncate_items(knowledge_items, personalization_budget)
        knowledge_tokens = sum(_estimate_tokens(item.content) for item in knowledge_items)
        personalization_budget = max(0, personalization_budget - knowledge_tokens)
        if len(knowledge_items) < original_knowledge_count:
            truncated = True

        # Truncate memory items
        original_memory_count = len(memory_items)
        memory_items[:] = _truncate_items(memory_items, personalization_budget)
        memory_tokens = sum(_estimate_tokens(item.content) for item in memory_items)
        personalization_budget = max(0, personalization_budget - memory_tokens)
        if len(memory_items) < original_memory_count:
            truncated = True

        # Truncate summary
        original_summary_count = len(summary)
        summary[:] = _truncate_text_list(summary, personalization_budget)
        summary_tokens = sum(_estimate_tokens(text) for text in summary)
        if len(summary) < original_summary_count:
            truncated = True

        used_tokens = (
            system_tokens
            + recent_tokens
            + profile_tokens
            + knowledge_tokens
            + memory_tokens
            + summary_tokens
        )

        if used_tokens > available_context_tokens:
            truncated = True

        sections = {
            "system": system_tokens,
            "recent_messages": recent_tokens,
            "summary": summary_tokens,
            "knowledge": knowledge_tokens,
            "memories": memory_tokens,
            "profile": profile_tokens,
        }
        for name, value in sections.items():
            if value == 0 and name not in ("system", "recent_messages"):
                dropped_sections.append(name)

        return TokenBudget(
            max_context_tokens=max_context_tokens,
            reserve_for_completion=reserve_for_completion,
            available_context_tokens=available_context_tokens,
            used_tokens=used_tokens,
            truncated=truncated,
            sections=sections,
            dropped_sections=dropped_sections,
        )

    def _get_config(self):
        return self._config or get_config()


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _truncate_text(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    if _estimate_tokens(text) <= max_tokens:
        return text
    max_chars = max_tokens * 4
    return text[:max_chars]


def _truncate_text_list(items: list[str], max_tokens: int) -> list[str]:
    if max_tokens <= 0:
        return []
    kept: list[str] = []
    tokens_used = 0
    for item in items:
        item_tokens = _estimate_tokens(item)
        if tokens_used + item_tokens > max_tokens:
            break
        kept.append(item)
        tokens_used += item_tokens
    return kept


def _truncate_items(items: list, max_tokens: int) -> list:
    if max_tokens <= 0:
        return []
    kept = []
    tokens_used = 0
    for item in items:
        item_tokens = _estimate_tokens(item.content)
        if tokens_used + item_tokens > max_tokens:
            break
        kept.append(item)
        tokens_used += item_tokens
    return kept


def _truncate_messages(messages: list[ChatMessage], max_tokens: int) -> list[ChatMessage]:
    if max_tokens <= 0:
        return []
    tokens_used = 0
    kept_reversed: list[ChatMessage] = []
    for message in reversed(messages):
        message_tokens = _estimate_tokens(message.content)
        if tokens_used + message_tokens > max_tokens:
            break
        kept_reversed.append(message)
        tokens_used += message_tokens
    return list(reversed(kept_reversed))

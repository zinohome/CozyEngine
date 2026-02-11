"""Convert a ContextBundle into AI engine messages."""

from app.context.models import ContextBundle
from app.engines.ai import ChatMessage


def context_to_messages(bundle: ContextBundle, current_message: str) -> list[ChatMessage]:
    """Convert context bundle to AI engine messages."""
    messages: list[ChatMessage] = []

    if bundle.system_prompts:
        messages.append(
            ChatMessage(
                role="system",
                content="\n\n".join(prompt for prompt in bundle.system_prompts if prompt),
            )
        )

    profile_text = _format_user_profile(bundle)
    if profile_text:
        messages.append(ChatMessage(role="system", content=profile_text))

    knowledge_text = _format_knowledge(bundle)
    if knowledge_text:
        messages.append(ChatMessage(role="system", content=knowledge_text))

    memory_text = _format_memories(bundle)
    if memory_text:
        messages.append(ChatMessage(role="system", content=memory_text))

    summary_text = _format_summaries(bundle)
    if summary_text:
        messages.append(ChatMessage(role="system", content=summary_text))

    messages.extend(bundle.recent_messages)
    messages.append(ChatMessage(role="user", content=current_message))

    return messages


def _format_user_profile(bundle: ContextBundle) -> str:
    profile = bundle.user_profile
    if not profile or not profile.profile_text:
        return ""
    return f"## User Profile\n{profile.profile_text}"


def _format_knowledge(bundle: ContextBundle) -> str:
    if not bundle.retrieved_knowledge:
        return ""
    lines = []
    for item in bundle.retrieved_knowledge:
        label = f"[{item.source}] " if item.source else ""
        lines.append(f"- {label}{item.content}")
    return "## Retrieved Knowledge\n" + "\n".join(lines)


def _format_memories(bundle: ContextBundle) -> str:
    if not bundle.retrieved_memories:
        return ""
    lines = [f"- {item.content}" for item in bundle.retrieved_memories]
    return "## Retrieved Memories\n" + "\n".join(lines)


def _format_summaries(bundle: ContextBundle) -> str:
    if not bundle.summarized_history:
        return ""
    summaries = "\n".join(f"- {summary}" for summary in bundle.summarized_history)
    return "## Conversation Summary\n" + summaries

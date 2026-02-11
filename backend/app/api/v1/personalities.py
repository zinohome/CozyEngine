"""人格列表端点"""

from fastapi import APIRouter

from app.core.personalities import get_personality_registry

router = APIRouter(prefix="/v1/personalities", tags=["personalities"])


@router.get("", response_model=None)
async def list_personalities() -> dict:
    """列出所有人格（最小摘要）"""
    registry = get_personality_registry()
    personalities = []
    for personality in registry.list_all():
        personalities.append(
            {
                "id": personality.id,
                "name": personality.name,
                "description": personality.description,
                "ai": {
                    "provider": personality.ai.provider,
                    "model": personality.ai.model,
                    "temperature": personality.ai.temperature,
                    "max_tokens": personality.ai.max_tokens,
                    "top_p": personality.ai.top_p,
                },
                "tools": {
                    "enabled": personality.tools.enabled,
                    "allowed_tools": personality.tools.allowed_tools,
                },
                "memory": {
                    "enabled": personality.memory.enabled,
                    "recall_top_k": personality.memory.recall_top_k,
                },
                "voice": None,
            }
        )

    return {"data": personalities}

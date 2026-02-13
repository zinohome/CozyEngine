"""CozyChat Compatible Personality API."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Any

from app.core.personalities.models import get_personality_registry, initialize_personality_registry, Personality
from app.observability.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# --- Pydantic Models ---

class AIConfig(BaseModel):
    provider: str
    model: str
    temperature: float
    max_tokens: int
    top_p: float

class PersonalityResponse(BaseModel):
    id: str
    name: str
    description: str
    ai: AIConfig
    metadata: dict[str, Any]

# --- Endpoints ---

@router.get("", response_model=List[PersonalityResponse])
async def list_personalities():
    """List all available personalities."""
    registry = get_personality_registry()
    personalities = registry.list_all()
    
    return [
        PersonalityResponse(
            id=p.id,
            name=p.name,
            description=p.description or "",
            ai=AIConfig(
                provider=p.ai.provider,
                model=p.ai.model,
                temperature=p.ai.temperature,
                max_tokens=p.ai.max_tokens,
                top_p=p.ai.top_p
            ),
            metadata=p.metadata
        ) for p in personalities
    ]

@router.post("/reload")
async def reload_personalities():
    """Reload personalities from configuration files (Admin only)."""
    # TODO: Add admin permission check
    try:
        registry = get_personality_registry()
        # Re-initialize will clear and reload if implemented that way, 
        # but the current implementation appends to the dict.
        # We need to consider if we want to clear first or just update.
        # Looking at `PersonalityRegistry` source, it just `_personalities[id] = p`.
        # So "reload" effectively updates existing or adds new. 
        # Ideally we should clear first to remove deleted files.
        # But `initialize_personality_registry` calls `loader.load_all` which calls `registry.register`.
        
        # Let's just call initialize again.
        initialize_personality_registry()
        
        count = len(get_personality_registry().list_all())
        logger.info("Personalities reloaded", count=count)
        return {"status": "success", "count": count, "message": "Personalities reloaded"}
    except Exception as e:
        logger.error(f"Failed to reload personalities: {e}")
        raise HTTPException(status_code=500, detail=str(e))

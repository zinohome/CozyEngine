"""人格模块"""

from app.core.personalities.models import (
    Personality,
    PersonalityLoader,
    PersonalityRegistry,
    get_personality_registry,
    initialize_personality_registry,
)

__all__ = [
    "Personality",
    "PersonalityRegistry",
    "PersonalityLoader",
    "get_personality_registry",
    "initialize_personality_registry",
]

"""API v1 路由"""

from app.api.v1.chat import router as chat_router
from app.api.v1.personalities import router as personalities_router

__all__ = ["chat_router", "personalities_router"]

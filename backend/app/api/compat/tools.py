"""CozyChat Compatible Tools API."""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from enum import Enum

from app.engines.tools.basic import BasicToolsEngine
from app.engines.tools import ToolDefinition
from app.observability.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# --- Pydantic Models ---
class ToolSchema(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]
    requires_permission: bool
    side_effect: str

# --- Endpoints ---

@router.get("", response_model=List[ToolSchema])
async def list_tools():
    """List all available tools."""
    engine = BasicToolsEngine()
    await engine.initialize()
    tools = engine.list_tools()
    
    return [
        ToolSchema(
            name=t.name,
            description=t.description,
            parameters=t.parameters,
            requires_permission=t.requires_permission,
            side_effect=t.side_effect.value
        ) for t in tools
    ]

@router.post("/refresh")
async def refresh_tools():
    """Trigger tool discovery/refresh (Admin only)."""
    # TODO: Add admin permission check
    # Currently just re-initializes a temporary engine to log count,
    # as there is no persistent tool engine state to refresh globally yet.
    # In a real implementation with MCP, this would trigger the MCP client discovery.
    
    engine = BasicToolsEngine()
    await engine.initialize()
    count = len(engine.list_tools())
    
    logger.info("Tools refreshed", count=count)
    return {"status": "success", "count": count, "message": "Tools refreshed"}

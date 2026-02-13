"""CozyChat Compatible Session API."""

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, update, and_, desc

from app.storage.database import db_manager, AsyncSession
from app.storage.models import Session, Message
from app.observability.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()

# --- Pydantic Models ---

class SessionCreate(BaseModel):
    personality_id: str
    title: Optional[str] = None
    metadata: dict[str, Any] = {}

class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    personality_id: str
    title: Optional[str]
    message_count: int
    created_at: datetime
    last_message_at: Optional[datetime]
    metadata: dict[str, Any]

class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    metadata: dict[str, Any]

# --- Endpoints ---

@router.post("", response_model=SessionResponse)
async def create_session(
    schema: SessionCreate,
    request: Request,
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Create a new chat session."""
    # TODO: Get real user_id from auth middleware
    user_id = getattr(request.state, "user_id", None) or uuid.UUID("00000000-0000-0000-0000-000000000000")
    
    # Ensure user_id is UUID
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)

    new_session = Session(
        user_id=user_id,
        personality_id=schema.personality_id,
        title=schema.title or "New Chat",
        session_metadata=schema.metadata
    )
    
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    
    logger.info("Session created", session_id=str(new_session.id), user_id=str(user_id))
    
    return SessionResponse(
        id=new_session.id,
        user_id=new_session.user_id,
        personality_id=new_session.personality_id,
        title=new_session.title,
        message_count=new_session.message_count,
        created_at=new_session.created_at,
        last_message_at=new_session.last_message_at,
        metadata=new_session.session_metadata
    )

@router.get("", response_model=List[SessionResponse])
async def list_sessions(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(db_manager.get_session)
):
    """List active sessions for the current user."""
    user_id = getattr(request.state, "user_id", None) or uuid.UUID("00000000-0000-0000-0000-000000000000")
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)

    stmt = (
        select(Session)
        .where(
            and_(
                Session.user_id == user_id,
                Session.deleted_at.is_(None)
            )
        )
        .order_by(desc(Session.last_message_at).nulls_last(), desc(Session.created_at))
        .limit(limit)
        .offset(offset)
    )
    
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    
    return [
        SessionResponse(
            id=s.id,
            user_id=s.user_id,
            personality_id=s.personality_id,
            title=s.title,
            message_count=s.message_count,
            created_at=s.created_at,
            last_message_at=s.last_message_at,
            metadata=s.session_metadata
        ) for s in sessions
    ]

@router.get("/{session_id}/messages", response_model=List[MessageResponse])
async def get_session_messages(
    session_id: UUID,
    request: Request,
    limit: int = 100,
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Get message history for a session."""
    user_id = getattr(request.state, "user_id", None) or uuid.UUID("00000000-0000-0000-0000-000000000000")
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)

    # Validate session ownership
    session_stmt = select(Session).where(
        and_(
            Session.id == session_id,
            Session.user_id == user_id,
            Session.deleted_at.is_(None)
        )
    )
    session_res = await db.execute(session_stmt)
    if not session_res.scalar_one_or_none():
         raise HTTPException(status_code=404, detail="Session not found")

    # Fetch messages
    msg_stmt = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    
    result = await db.execute(msg_stmt)
    messages = result.scalars().all()
    
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at,
            metadata=m.message_metadata
        ) for m in messages
    ]

@router.delete("/{session_id}")
async def delete_session(
    session_id: UUID,
    request: Request,
    db: AsyncSession = Depends(db_manager.get_session)
):
    """Soft delete a session."""
    user_id = getattr(request.state, "user_id", None) or uuid.UUID("00000000-0000-0000-0000-000000000000")
    if isinstance(user_id, str):
        user_id = uuid.UUID(user_id)

    stmt = select(Session).where(
        and_(
            Session.id == session_id,
            Session.user_id == user_id
        )
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    
    logger.info("Session soft deleted", session_id=str(session_id))
    return {"status": "success", "id": str(session_id)}

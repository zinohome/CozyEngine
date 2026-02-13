"""Tests for Compatibility API Routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

# Setup Mocks BEFORE importing app if possible, or patch existing modules
from app.storage.database import db_manager
from app.storage.redis import redis_manager
from app.services.worker import async_worker
from app.storage.models import Session as SessionModel, Message as MessageModel

# Mock lifecycle methods to avoid real connection attempts
db_manager.initialize = MagicMock()
db_manager.close = AsyncMock()
redis_manager.initialize = AsyncMock()
redis_manager.close = AsyncMock()
async_worker.start = AsyncMock()
async_worker.stop = AsyncMock()
# Mock engine registry to avoid loading real models
from app.engines.registry import engine_registry
engine_registry.close_all = AsyncMock()

from fastapi.testclient import TestClient
from app.main import app

# Create mock DB session
mock_db = AsyncMock()

async def mock_get_session():
    yield mock_db

app.dependency_overrides[db_manager.get_session] = mock_get_session

@pytest.fixture
def client():
    # Use context manager to trigger lifespan (which calls our mocks)
    with TestClient(app) as client:
        yield client

def test_list_personalities_compat(client):
    """Test GET /api/v1/personalities"""
    response = client.get("/api/v1/personalities")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if len(data) > 0:
        p = data[0]
        assert "id" in p
        assert "name" in p

def test_list_tools_compat(client):
    """Test GET /api/v1/tools"""
    response = client.get("/api/v1/tools")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    
def test_list_sessions_compat(client):
    """Test GET /api/v1/chat/sessions"""
    # Setup mock return
    mock_session_obj = SessionModel(
        id=uuid4(),
        user_id=uuid4(),
        personality_id="test_p",
        title="Mock Session",
        created_at=datetime.utcnow(),
        last_message_at=datetime.utcnow(),
        message_count=5,
        session_metadata={}
    )
    
    # Mock result.scalars().all()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_session_obj]
    mock_db.execute.return_value = mock_result

    response = client.get("/api/v1/chat/sessions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Mock Session"

def test_create_session_compat(client):
    """Test POST /api/v1/chat/sessions"""
    # Mock behavior for add/commit/refresh
    # We need to set the ID on the new session object when added
    def side_effect_add(obj):
        if not obj.id:
            obj.id = uuid4()
        if not obj.created_at:
            obj.created_at = datetime.utcnow()
        if getattr(obj, "message_count", None) is None:
            obj.message_count = 0
    
    # db.add is synchronous in SQLAlchemy
    mock_db.add = MagicMock(side_effect=side_effect_add)
    # db.commit/refresh are async
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    
    payload = {
        "personality_id": "cozy_companion", 
        "title": "Created Session",
        "metadata": {"test": True}
    }
    response = client.post("/api/v1/chat/sessions", json=payload)
    
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Created Session"
    assert "id" in data
    
def test_delete_session_compat(client):
    """Test DELETE /api/v1/chat/sessions/{id}"""
    session_id = uuid4()
    
    # Mock finding the session
    mock_session_obj = SessionModel(
        id=session_id,
        user_id=uuid4(), # Should match default user in endpoint
        deleted_at=None
    )
    # The endpoint uses UUID("0000...") default user if not auth
    mock_session_obj.user_id = uuid4() # this might not match exactly if UUID generation differs logic
    # But endpoint uses `or uuid.UUID("0000...")`.
    # And we mocked get_session. 
    # But `Session` object creation in endpoint sets user_id. 
    # The delete endpoint queries `where user_id == ...`.
    # `mock_db.execute` returns whatever we say.
    
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_session_obj
    mock_db.execute.return_value = mock_result
    
    response = client.delete(f"/api/v1/chat/sessions/{session_id}")
    assert response.status_code == 200 
    
    # Verify soft delete
    assert mock_session_obj.deleted_at is not None

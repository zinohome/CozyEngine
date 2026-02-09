"""Tests for database models and operations"""


import pytest
from sqlalchemy import select

from app.storage.database import DatabaseManager
from app.storage.models import AuditEvent, Message, Session, User


@pytest.fixture
async def db_manager():
    """Create a test database manager"""
    manager = DatabaseManager()
    manager.initialize()
    yield manager
    await manager.close()


@pytest.fixture
async def db_session(db_manager):
    """Create a test database session"""
    async with db_manager.session() as session:
        yield session


@pytest.mark.asyncio
async def test_create_user(db_session):
    """Test creating a user"""
    user = User(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        role="user",
        status="active",
    )

    db_session.add(user)
    await db_session.commit()

    # Verify user was created
    assert user.id is not None
    assert user.username == "testuser"
    assert user.created_at is not None


@pytest.mark.asyncio
async def test_create_session(db_session):
    """Test creating a session"""
    # Create a user first
    user = User(
        username="sessionuser",
        email="session@example.com",
        password_hash="hashed_password",
    )
    db_session.add(user)
    await db_session.commit()

    # Create a session
    session_obj = Session(
        user_id=user.id,
        personality_id="default",
        title="Test Session",
        message_count=0,
    )
    db_session.add(session_obj)
    await db_session.commit()

    # Verify session was created
    assert session_obj.id is not None
    assert session_obj.user_id == user.id
    assert session_obj.personality_id == "default"
    assert session_obj.deleted_at is None  # Not soft-deleted


@pytest.mark.asyncio
async def test_create_message(db_session):
    """Test creating a message"""
    # Create user and session
    user = User(
        username="msguser", email="msg@example.com", password_hash="hashed_password"
    )
    db_session.add(user)
    await db_session.commit()

    session_obj = Session(
        user_id=user.id, personality_id="default", title="Test Session"
    )
    db_session.add(session_obj)
    await db_session.commit()

    # Create message
    message = Message(
        session_id=session_obj.id,
        user_id=user.id,
        role="user",
        content="Hello, world!",
        message_metadata={"test": "value"},
    )
    db_session.add(message)
    await db_session.commit()

    # Verify message was created
    assert message.id is not None
    assert message.role == "user"
    assert message.content == "Hello, world!"
    assert message.message_metadata == {"test": "value"}


@pytest.mark.asyncio
async def test_create_audit_event(db_session):
    """Test creating an audit event"""
    event = AuditEvent(
        request_id="test-request-id",
        event_type="TEST_EVENT",
        payload={"action": "test", "result": "success"},
    )
    db_session.add(event)
    await db_session.commit()

    # Verify event was created
    assert event.id is not None
    assert event.request_id == "test-request-id"
    assert event.event_type == "TEST_EVENT"


@pytest.mark.asyncio
async def test_soft_delete_session(db_session):
    """Test soft delete for sessions"""
    from datetime import datetime

    # Create user and session
    user = User(
        username="deleteuser",
        email="delete@example.com",
        password_hash="hashed_password",
    )
    db_session.add(user)
    await db_session.commit()

    session_obj = Session(user_id=user.id, personality_id="default")
    db_session.add(session_obj)
    await db_session.commit()

    session_id = session_obj.id

    # Soft delete the session
    session_obj.deleted_at = datetime.utcnow()
    await db_session.commit()

    # Verify session is soft-deleted
    result = await db_session.execute(
        select(Session).where(Session.id == session_id)
    )
    deleted_session = result.scalar_one_or_none()
    assert deleted_session is not None
    assert deleted_session.deleted_at is not None


@pytest.mark.asyncio
async def test_query_messages_by_session(db_session):
    """Test querying messages by session"""
    # Create user and session
    user = User(
        username="queryuser", email="query@example.com", password_hash="hashed_password"
    )
    db_session.add(user)
    await db_session.commit()

    session_obj = Session(user_id=user.id, personality_id="default")
    db_session.add(session_obj)
    await db_session.commit()

    # Create multiple messages
    for i in range(3):
        message = Message(
            session_id=session_obj.id,
            user_id=user.id,
            role="user",
            content=f"Message {i}",
        )
        db_session.add(message)
    await db_session.commit()

    # Query messages
    result = await db_session.execute(
        select(Message)
        .where(Message.session_id == session_obj.id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()

    assert len(messages) == 3
    assert messages[0].content == "Message 0"
    assert messages[2].content == "Message 2"

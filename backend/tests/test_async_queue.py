import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.storage.queue import task_queue
from app.services.worker import async_worker
from app.engines.user_profile.memobase import MemobaseUserProfileEngine

@pytest.fixture
def mock_redis():
    mock_client = AsyncMock()
    with patch("app.storage.redis.redis_manager.get_client", return_value=mock_client):
        yield mock_client

@pytest.fixture
def mock_engine_registry():
    with patch("app.services.worker.engine_registry") as mock:
        yield mock

@pytest.mark.asyncio
async def test_enqueue_success(mock_redis):
    payload = {"foo": "bar"}
    result = await task_queue.enqueue("test_queue", payload)
    assert result is True
    mock_redis.lpush.assert_called_once()

@pytest.mark.asyncio
async def test_enqueue_failure_no_redis():
    with patch("app.storage.redis.redis_manager.get_client", return_value=None):
        result = await task_queue.enqueue("test_queue", {})
        assert result is False

@pytest.mark.asyncio
async def test_dequeue_success(mock_redis):
    # redis.brpop returns (key, value)
    mock_redis.brpop.return_value = (b"test_queue", b'{"foo": "bar"}')
    result = await task_queue.dequeue("test_queue")
    assert result == {"foo": "bar"}

@pytest.mark.asyncio
async def test_dequeue_empty(mock_redis):
    mock_redis.brpop.return_value = None
    result = await task_queue.dequeue("test_queue")
    assert result is None

@pytest.mark.asyncio
async def test_worker_profile_update(mock_engine_registry):
    # Setup mock engine
    mock_engine = AsyncMock()
    # Ensure it passes verify_structure check if we used strict typing, 
    # but here we use hasattr, so mock needs to have the method
    mock_engine._perform_update = AsyncMock()
    
    mock_engine_registry.get_user_profile_engine.return_value = mock_engine
    
    payload = {"user_id": "u1", "messages": []}
    await async_worker._handle_profile_update(payload)
    
    mock_engine._perform_update.assert_called_once_with(payload)

@pytest.mark.asyncio
async def test_worker_memory_update(mock_engine_registry):
    mock_engine = AsyncMock()
    mock_engine._perform_add = AsyncMock()
    mock_engine_registry.get_chat_memory_engine.return_value = mock_engine
    
    payload = {"session_id": "s1", "messages": []}
    await async_worker._handle_memory_update(payload)
    
    mock_engine._perform_add.assert_called_once_with(payload)

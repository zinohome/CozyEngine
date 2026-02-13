import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.engines.knowledge.cognee import CogneeKnowledgeEngine
from app.engines.knowledge import KnowledgeItem
from app.engines.base_remote import L1Cache, CircuitBreaker
from app.storage.redis import redis_manager

# Mock redis_manager to avoid real Redis connection in tests
redis_manager._redis = AsyncMock()

@pytest.fixture
def mock_httpx_client():
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value = mock_client
        yield mock_client

@pytest.fixture
def cognee_engine():
    return CogneeKnowledgeEngine(api_url="http://cognee.test", api_token="test-token")

@pytest.mark.asyncio
async def test_cognee_search_success(cognee_engine, mock_httpx_client):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "content": "Test knowledge",
                "score": 0.9,
                "dataset": "default",
                "metadata": {"source": "test"}
            }
        ]
    }
    mock_httpx_client.post.return_value = mock_response

    # Initialize engine (creates client)
    await cognee_engine.initialize()
    
    # Execute search
    results = await cognee_engine.search_knowledge("test query")
    
    # Verify results
    assert len(results) == 1
    assert isinstance(results[0], KnowledgeItem)
    assert results[0].content == "Test knowledge"
    assert results[0].score == 0.9
    
    # Verify cache
    cache_key = "engine:search:test query:5:"
    assert cognee_engine.l1_cache.get(cache_key) is not None

@pytest.mark.asyncio
async def test_cognee_search_failure_fallback(cognee_engine, mock_httpx_client):
    # Setup mock generic exception
    mock_httpx_client.post.side_effect = Exception("API Error")

    await cognee_engine.initialize()
    results = await cognee_engine.search_knowledge("test query")
    
    # Should fallback to empty list
    assert results == []
    assert cognee_engine.circuit_breaker.failure_count == 1

@pytest.mark.asyncio
async def test_circuit_breaker_open(cognee_engine, mock_httpx_client):
    # Force circuit breaker open
    cognee_engine.circuit_breaker.state = "OPEN"
    cognee_engine.circuit_breaker.last_failure_time = time.time()
    
    await cognee_engine.initialize()
    results = await cognee_engine.search_knowledge("test query")
    
    # Should fail fast without calling API
    assert results == []
    mock_httpx_client.post.assert_not_called()

@pytest.mark.asyncio
async def test_l1_cache_hit(cognee_engine, mock_httpx_client):
    # Pre-populate L1 cache
    cache_key = "engine:search:test query:5:"
    item = KnowledgeItem(content="Cached content", score=1.0)
    cognee_engine.l1_cache.set(cache_key, [item])
    
    await cognee_engine.initialize()
    results = await cognee_engine.search_knowledge("test query")
    
    # Should return from cache
    assert len(results) == 1
    assert results[0].content == "Cached content"
    mock_httpx_client.post.assert_not_called()

@pytest.mark.asyncio
async def test_l2_cache_hit(cognee_engine, mock_httpx_client):
    # Ensure L1 miss
    cache_key = "engine:search:test query:5:"
    
    # Setup L2 (Redis) hit
    redis_manager._redis.get.return_value = json.dumps([
        {
            "content": "Redis content",
            "score": 0.95,
            "source": None,
            "dataset_name": None,
            "metadata": {}
        }
    ])
    
    await cognee_engine.initialize()
    results = await cognee_engine.search_knowledge("test query")
    
    # Should return from Redis and populate L1
    assert len(results) == 1
    assert results[0].content == "Redis content"
    assert cognee_engine.l1_cache.get(cache_key) is not None
    mock_httpx_client.post.assert_not_called()
    

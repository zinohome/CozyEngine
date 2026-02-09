"""Basic health check test."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "CozyEngine"
    assert data["status"] == "operational"


def test_health_check_v1():
    """Test health check endpoint (v1 API)"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert "services" in data
    assert isinstance(data["services"], list)

    # Check database service
    db_service = next((s for s in data["services"] if s["name"] == "database"), None)
    assert db_service is not None
    assert db_service["status"] in ["healthy", "degraded", "unhealthy"]


def test_readiness_check():
    """Test readiness probe endpoint"""
    response = client.get("/api/v1/health/ready")
    # Should return 200 if database is connected, or 503 if not
    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "ready"


def test_liveness_check():
    """Test liveness probe endpoint"""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "alive"

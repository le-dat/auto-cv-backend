from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """
    Simple health check test to verify the test environment is working.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

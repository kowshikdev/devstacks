from fastapi.testclient import TestClient

from devstacks_api.main import app


def test_health_reports_service_readiness():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
from fastapi.testclient import TestClient

from proseforge.api.main import create_app


def test_liveness_is_available():
    response = TestClient(create_app()).get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

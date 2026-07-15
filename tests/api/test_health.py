from fastapi.testclient import TestClient

from proseforge.api.main import create_app


def test_liveness_is_available():
    response = TestClient(create_app()).get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_storage_checks():
    response = TestClient(create_app()).get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json()["checks"]["blob_root"] == "ok"
    assert response.json()["checks"]["master_key"] == "ok"
    assert response.json()["checks"]["pgvector"] == "ok"
    assert response.json()["checks"]["partial_messages"] == "ok"


def test_logout_clears_session_cookie_without_database_access():
    response = TestClient(create_app()).post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert "proseforge_session" in response.headers.get("set-cookie", "")

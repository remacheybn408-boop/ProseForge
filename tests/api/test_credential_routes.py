from fastapi.testclient import TestClient

from proseforge.api.main import create_app


def test_credential_listing_requires_authentication():
    response = TestClient(create_app()).get("/api/v1/credentials")
    assert response.status_code == 401


def test_credential_deletion_requires_authentication():
    response = TestClient(create_app()).delete("/api/v1/credentials/credential-1")
    assert response.status_code == 401

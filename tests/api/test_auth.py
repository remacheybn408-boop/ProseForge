from fastapi.testclient import TestClient

from proseforge.api.main import create_app


class DenyLogin:
    async def allow(self, identity: str) -> bool:
        return False


def test_login_is_rate_limited_before_database_lookup():
    application = create_app()
    application.state.login_rate_limiter = DenyLogin()

    response = TestClient(application).post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "a-secure-password"},
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"

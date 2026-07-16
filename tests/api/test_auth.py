from fastapi.testclient import TestClient

from proseforge.api.main import create_app
from proseforge.settings import Settings


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


def test_login_rate_limit_uses_configured_attempt_budget():
    application = create_app(Settings(login_rate_limit_attempts=17))

    assert application.state.login_rate_limiter.max_attempts == 17

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGIN = "http://testserver"
SETUP_EMAIL = "t@example.local"
SETUP_PASSWORD = "twelve-char-pw"


@pytest.fixture(scope="session")
def api_settings(tmp_path_factory):
    database_url = os.environ.get("PROSEFORGE_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("PROSEFORGE_TEST_DATABASE_URL is required (API tests run in the B1 batch)")
    from proseforge.settings import Settings

    return Settings(
        database_url=database_url,
        public_url=ORIGIN,
        blob_root=str(tmp_path_factory.mktemp("blobs")),
        backup_root=str(tmp_path_factory.mktemp("backups")),
        data_dir=str(tmp_path_factory.mktemp("data")),
        runtime_profile="test",
    )


@pytest.fixture(scope="session")
def client(api_settings):
    sync_url = os.environ.get("PROSEFORGE_SYNC_DATABASE_URL")
    if not sync_url:
        pytest.skip("PROSEFORGE_SYNC_DATABASE_URL is required (API tests run in the B1 batch)")
    from alembic import command
    from alembic.config import Config

    from proseforge.api.main import create_app

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "proseforge" / "infrastructure" / "database" / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", sync_url)
    command.upgrade(alembic_cfg, "head")  # 顺便验证迁移链
    # 必须走上下文管理器：裸 TestClient 每个请求新开 anyio portal（独立事件循环），
    # 跨请求复用的 asyncpg 连接会报 "attached to a different loop"。
    # with 块内整个会话共享一个 portal，并运行 lifespan（启动真实生命周期）。
    with TestClient(create_app(api_settings)) as test_client:
        yield test_client


class AuthClient:
    """TestClient wrapper that injects the Origin header require_same_origin expects."""

    def __init__(self, client: TestClient):
        self._client = client

    @property
    def raw(self) -> TestClient:
        return self._client

    def get(self, url: str, **kwargs):
        return self._client.get(url, **kwargs)

    def stream(self, method: str, url: str, **kwargs):
        return self._client.stream(method, url, **kwargs)

    def post_json(self, url: str, payload: dict):
        return self._client.post(url, json=payload, headers={"Origin": ORIGIN})

    def post(self, url: str, **kwargs):
        headers = {"Origin": ORIGIN, **kwargs.pop("headers", {})}
        return self._client.post(url, headers=headers, **kwargs)


@pytest.fixture()
def auth_client(client):
    response = client.post("/api/v1/auth/setup", json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD}, headers={"Origin": ORIGIN})
    assert response.status_code in (201, 409)  # 会话内只首个用例 201
    # setup 不签发会话 cookie，必须显式登录
    login = client.post("/api/v1/auth/login", json={"email": SETUP_EMAIL, "password": SETUP_PASSWORD}, headers={"Origin": ORIGIN})
    assert login.status_code == 200
    return AuthClient(client)

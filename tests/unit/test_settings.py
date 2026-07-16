import pytest
from pydantic import ValidationError

from proseforge.settings import Settings


def test_production_rejects_placeholder_secrets():
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            database_url="postgresql+asyncpg://x",
            redis_url="redis://x",
            master_key="replace-with-32-byte-base64-key",
            jwt_secret="replace-with-long-random-secret",
        )


def test_development_allows_local_defaults():
    settings = Settings(
        environment="development",
        database_url="postgresql+asyncpg://x",
        redis_url="redis://x",
    )
    assert settings.environment == "development"

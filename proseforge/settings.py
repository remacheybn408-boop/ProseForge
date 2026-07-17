from __future__ import annotations

import base64
import binascii
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROSEFORGE_",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"
    public_url: str = "http://localhost:3000"
    database_url: str = "postgresql+asyncpg://proseforge:proseforge@postgres:5432/proseforge"
    sync_database_url: str = ""
    redis_url: str = "redis://redis:6379/0"
    blob_root: str = "/data/blobs"
    backup_root: str = "/data/backups"
    master_key: SecretStr = SecretStr("replace-with-32-byte-base64-key")
    jwt_secret: SecretStr = SecretStr("replace-with-long-random-secret")
    bootstrap_admin_email: str = "admin@example.local"
    bootstrap_admin_password: SecretStr = SecretStr("change-me-now")
    max_upload_bytes: int = 50 * 1024 * 1024
    allowed_local_provider_hosts: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        if self.environment.lower() not in {"production", "prod"}:
            return self

        placeholders = {
            "replace-with-32-byte-base64-key",
            "replace-with-long-random-secret",
            "change-me-now",
        }
        if self.master_key.get_secret_value() in placeholders:
            raise ValueError("PROSEFORGE_MASTER_KEY must be replaced in production")
        if self.jwt_secret.get_secret_value() in placeholders:
            raise ValueError("PROSEFORGE_JWT_SECRET must be replaced in production")
        if len(self.jwt_secret.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("PROSEFORGE_JWT_SECRET must be at least 32 bytes")
        try:
            decoded = base64.b64decode(self.master_key.get_secret_value(), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("PROSEFORGE_MASTER_KEY must be valid base64") from exc
        if len(decoded) != 32:
            raise ValueError("PROSEFORGE_MASTER_KEY must decode to 32 bytes")
        for name, value in (("blob_root", self.blob_root), ("backup_root", self.backup_root)):
            if not Path(value).is_absolute():
                raise ValueError(f"{name} must be absolute in production")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

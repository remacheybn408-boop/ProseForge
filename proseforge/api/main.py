from fastapi import FastAPI

from proseforge.api.routes.health import router as health_router
from proseforge.api.routes.auth import router as auth_router
from proseforge.application.auth.service import AuthService

from proseforge.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    application = FastAPI(title="ProseForge API", version="1.0.0")
    application.state.settings = resolved
    application.state.auth = AuthService(resolved.jwt_secret.get_secret_value())
    application.include_router(health_router)
    application.include_router(auth_router)
    return application


app = create_app()


def get_auth_service() -> AuthService:
    return app.state.auth

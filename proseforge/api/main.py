from fastapi import FastAPI

from proseforge.api.routes.health import router as health_router
from proseforge.api.routes.auth import router as auth_router
from proseforge.api.routes.projects import router as projects_router
from proseforge.api.routes.conversations import router as conversations_router
from proseforge.api.routes.providers import router as providers_router
from proseforge.api.routes.workflows import router as workflows_router
from proseforge.api.routes.files import router as files_router
from proseforge.api.routes.chapters import router as chapters_router
from proseforge.api.routes.exports import router as exports_router
from proseforge.api.routes.credentials import router as credentials_router
from proseforge.api.routes.outlines import router as outlines_router
from proseforge.api.routes.context import router as context_router
from proseforge.application.auth.service import AuthService
from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
from proseforge.infrastructure.events.database import DatabaseEventStream
from proseforge.infrastructure.tasks.memory import InMemoryTaskQueue
from proseforge.providers.registry import ProviderRegistry

from proseforge.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    application = FastAPI(title="ProseForge API", version="1.0.0")
    application.state.settings = resolved
    application.state.auth = AuthService(resolved.jwt_secret.get_secret_value())
    application.state.engine, application.state.session_factory = create_engine_and_sessionmaker(resolved)
    application.state.event_stream = DatabaseEventStream(application.state.session_factory)
    application.state.queue = InMemoryTaskQueue()
    application.state.provider_registry = ProviderRegistry()
    application.state.model_catalog = {}
    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(projects_router)
    application.include_router(conversations_router)
    application.include_router(providers_router)
    application.include_router(workflows_router)
    application.include_router(files_router)
    application.include_router(chapters_router)
    application.include_router(exports_router)
    application.include_router(credentials_router)
    application.include_router(outlines_router)
    application.include_router(context_router)
    return application


app = create_app()


def get_auth_service() -> AuthService:
    return app.state.auth

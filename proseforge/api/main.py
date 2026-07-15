from fastapi import FastAPI

from proseforge.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    application = FastAPI(title="ProseForge API", version="1.0.0")
    application.state.settings = resolved
    return application


app = create_app()

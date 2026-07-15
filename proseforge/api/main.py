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
from proseforge.api.routes.model_profiles import router as model_profiles_router
from proseforge.application.auth.service import AuthService
from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
from proseforge.infrastructure.events.database import DatabaseEventStream
from proseforge.infrastructure.tasks.celery import CeleryTaskQueue
from proseforge.providers.registry import ProviderRegistry
from proseforge.providers.anthropic import AnthropicProvider
from proseforge.providers.baidu import BaiduProvider
from proseforge.providers.cohere import CohereProvider
from proseforge.providers.dashscope import DashScopeProvider
from proseforge.providers.deepseek import DeepSeekProvider
from proseforge.providers.google import GoogleProvider
from proseforge.providers.kimi import KimiProvider
from proseforge.providers.minimax import MiniMaxProvider
from proseforge.providers.mistral import MistralProvider
from proseforge.providers.ollama import OllamaProvider
from proseforge.providers.openai import OpenAIProvider
from proseforge.providers.tencent import TencentProvider
from proseforge.providers.volcengine import VolcEngineProvider
from proseforge.providers.vllm import VLLMProvider
from proseforge.providers.xai import XAIProvider
from proseforge.providers.zhipu import ZhipuProvider

from proseforge.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    application = FastAPI(title="ProseForge API", version="1.0.0")
    application.state.settings = resolved
    application.state.auth = AuthService(resolved.jwt_secret.get_secret_value())
    application.state.engine, application.state.session_factory = create_engine_and_sessionmaker(resolved)
    application.state.event_stream = DatabaseEventStream(application.state.session_factory)
    application.state.queue = CeleryTaskQueue()
    registry = ProviderRegistry()
    for provider in (
        OpenAIProvider(""), AnthropicProvider(""), GoogleProvider(""), DeepSeekProvider(), KimiProvider(),
        DashScopeProvider(), ZhipuProvider(), VolcEngineProvider(), BaiduProvider(), TencentProvider(),
        MiniMaxProvider(), XAIProvider(), MistralProvider(), CohereProvider(), OllamaProvider(), VLLMProvider(),
    ):
        registry.register(provider)
    application.state.provider_registry = registry
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
    application.include_router(model_profiles_router)
    return application


app = create_app()


def get_auth_service() -> AuthService:
    return app.state.auth

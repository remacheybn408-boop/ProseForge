from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from proseforge.api.middleware import CorrelationIdMiddleware
from proseforge.api.routes.auth import router as auth_router
from proseforge.api.routes.branches import router as branches_router
from proseforge.api.routes.chapters import router as chapters_router
from proseforge.api.routes.conversations import router as conversations_router
from proseforge.api.routes.context import router as context_router
from proseforge.api.routes.credentials import router as credentials_router
from proseforge.api.routes.exports import router as exports_router
from proseforge.api.routes.files import router as files_router
from proseforge.api.routes.health import router as health_router
from proseforge.api.routes.model_capabilities import router as model_capabilities_router
from proseforge.api.routes.maintenance import router as maintenance_router
from proseforge.api.routes.model_profiles import router as model_profiles_router
from proseforge.api.routes.outlines import router as outlines_router
from proseforge.api.routes.projects import router as projects_router
from proseforge.api.routes.providers import router as providers_router
from proseforge.api.routes.runtime import router as runtime_router
from proseforge.api.routes.static_web import router as static_web_router
from proseforge.api.routes.story_bible import router as story_bible_router
from proseforge.api.routes.usage import router as usage_router
from proseforge.api.routes.workflows import router as workflows_router
from proseforge.application.auth.service import AuthService
from proseforge.infrastructure.database.bootstrap import ensure_schema
from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
from proseforge.infrastructure.events.database import DatabaseEventStream
from proseforge.infrastructure.scheduler.local import LocalScheduler
from proseforge.infrastructure.tasks.factory import create_task_queue
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
from proseforge.providers.registry import ProviderRegistry
from proseforge.providers.tencent import TencentProvider
from proseforge.providers.volcengine import VolcEngineProvider
from proseforge.providers.vllm import VLLMProvider
from proseforge.providers.xai import XAIProvider
from proseforge.providers.zhipu import ZhipuProvider
from proseforge.runtime.bootstrap import bootstrap_runtime
from proseforge.runtime.factory import create_runtime
from proseforge.runtime.lifecycle import RuntimeLifecycle
from proseforge.runtime.paths import resolve_paths
from proseforge.runtime.profile import RuntimeProfile, capabilities_for
from proseforge.settings import Settings, get_settings


class _NoopScheduler:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


def _bootstrap_runtime(settings: Settings) -> None:
    env = dict(os.environ)
    if settings.data_dir:
        env["PROSEFORGE_DATA_DIR"] = settings.data_dir
    env["PROSEFORGE_DATABASE_URL"] = settings.database_url
    env["PROSEFORGE_BLOB_ROOT"] = settings.blob_root
    env["PROSEFORGE_BACKUP_ROOT"] = settings.backup_root
    profile = RuntimeProfile(settings.runtime_profile)
    paths = resolve_paths(profile, env)
    bootstrap_runtime(paths, profile)
    ensure_schema(settings)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        await application.state.lifecycle.start()
        try:
            yield
        finally:
            await application.state.lifecycle.stop()

    application = FastAPI(title="ProseForge API", version="1.0.0", lifespan=lifespan)
    application.add_middleware(CorrelationIdMiddleware)
    application.state.settings = resolved
    application.state.runtime = create_runtime(resolved)
    application.state.auth = AuthService(resolved.jwt_secret.get_secret_value())
    application.state.engine, application.state.session_factory = create_engine_and_sessionmaker(resolved)
    application.state.event_stream = DatabaseEventStream(application.state.session_factory)
    application.state.queue = create_task_queue(resolved, application.state.session_factory)

    async def maintenance_tick() -> None:
        recover_expired = getattr(application.state.queue, "recover_expired", None)
        if recover_expired is not None:
            await recover_expired()

    capabilities = capabilities_for(RuntimeProfile(resolved.runtime_profile))
    scheduler = (
        LocalScheduler(
            maintenance_tick,
            interval_seconds=max(1.0, resolved.native_queue_poll_seconds),
        )
        if capabilities.queue == "local"
        else _NoopScheduler()
    )
    application.state.lifecycle = RuntimeLifecycle(
        bootstrap=lambda: _bootstrap_runtime(resolved),
        queue=application.state.queue,
        scheduler=scheduler,
        engine=application.state.engine,
    )

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
    application.include_router(model_capabilities_router)
    application.include_router(auth_router)
    application.include_router(branches_router)
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
    application.include_router(maintenance_router)
    application.include_router(usage_router)
    application.include_router(runtime_router)
    application.include_router(static_web_router)
    application.include_router(story_bible_router)
    return application


app = create_app()


def get_auth_service() -> AuthService:
    return app.state.auth

"""ResearchOS FastAPI Gateway application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gateway.app.config import get_settings
from gateway.app.middleware.request_id import RequestIdMiddleware
from gateway.app.routers import auth, chat, health, knowledge, plc, research, sessions
from gateway.app.routers import settings as settings_router
from gateway.app.services.runtime_client import RuntimeClient
from gateway.app.ws import research as ws_research
from researchos_shared import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("researchos.gateway")
    runtime = RuntimeClient(settings.runtime_base_url)
    await runtime.startup()
    app.state.runtime_client = runtime
    logger.info(
        "gateway started env=%s runtime=%s litellm=%s",
        settings.env,
        settings.runtime_base_url or "local_echo",
        settings.litellm_base_url or "unset",
    )
    try:
        yield
    finally:
        await runtime.shutdown()
        logger.info("gateway stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ResearchOS Gateway",
        version="0.1.0",
        description="Auth, sessions, research/knowledge/PLC API boundary.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(research.router)
    app.include_router(chat.router)
    app.include_router(knowledge.router)
    app.include_router(plc.router)
    app.include_router(settings_router.router)
    app.include_router(ws_research.router)

    @app.get("/")
    async def root() -> dict[str, str]:
        return {"service": "researchos-gateway", "docs": "/docs"}

    return app


app = create_app()


def run() -> None:
    """Console entrypoint: researchos-gateway."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "gateway.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.is_dev,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()

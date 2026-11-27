"""Multiverse FastAPI Control Plane entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.core.config import get_settings
from services.api.core.database import init_db
from services.api.routes import apps, assistant, atlas, auth, passport, runtime, system, verse


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Multiverse Control Plane API",
        version="1.0.0",
        description="Open-source behavioural infrastructure powered by Flagsmith.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(dict.fromkeys([settings.app_base_url, *settings.allowed_cors_origins_list])),
        allow_origin_regex=settings.allowed_cors_origin_regex or None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system.router)
    app.include_router(auth.router)
    app.include_router(apps.router)
    app.include_router(atlas.router)
    app.include_router(verse.router)
    app.include_router(passport.router)
    app.include_router(runtime.router)
    app.include_router(assistant.router)

    return app


app = create_app()

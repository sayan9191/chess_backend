"""
FastAPI application entry point.

Initializes middleware, routes, exception handlers, and Swagger documentation.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, game, health, user
from app.core.config import get_settings
from app.core.database import engine
from app.core.logger import setup_logging
from app.middleware.exception_handlers import register_exception_handlers
from app.middleware.logging_middleware import LoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Production-ready Chess Backend API with WebSocket support",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(LoggingMiddleware)

    register_exception_handlers(app)

    app.include_router(health.router, prefix="/api/v1")
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(user.router, prefix="/api/v1")
    app.include_router(game.router, prefix="/api/v1")

    @app.get("/", tags=["Root"])
    async def root() -> dict:
        return {
            "success": True,
            "message": "Chess Backend API",
            "docs": "/docs",
        }

    return app


app = create_app()

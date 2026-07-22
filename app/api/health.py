"""Health check endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import APIResponse
from app.services.websocket_session_manager import session_manager

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="Health check")
async def health_check() -> APIResponse[dict]:
    settings = get_settings()
    return APIResponse(
        success=True,
        message="Service is healthy",
        data={
            "status": "ok",
            "app_name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "active_websocket_sessions": session_manager.active_count(),
        },
    )


@router.get("/sessions", summary="List active WebSocket game sessions")
async def active_sessions() -> APIResponse[dict]:
    return APIResponse(
        success=True,
        message="Active sessions retrieved",
        data={
            "count": session_manager.active_count(),
            "sessions": session_manager.list_sessions(),
        },
    )

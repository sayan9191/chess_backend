"""Global exception handlers returning consistent JSON error responses."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logger import get_logger
from app.schemas.common import ErrorDetail, ErrorResponse
from app.utils.exceptions import AppException

logger = get_logger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        body = ErrorResponse(
            success=False,
            message=exc.message,
            error=ErrorDetail(code=exc.code, message=exc.message, details=exc.details),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        body = ErrorResponse(
            success=False,
            message="Request validation failed",
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"errors": exc.errors()},
            ),
        )
        return JSONResponse(status_code=422, content=body.model_dump())

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        body = ErrorResponse(
            success=False,
            message=str(exc.detail),
            error=ErrorDetail(code="HTTP_ERROR", message=str(exc.detail)),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        body = ErrorResponse(
            success=False,
            message="Internal server error",
            error=ErrorDetail(code="INTERNAL_ERROR", message="Internal server error"),
        )
        return JSONResponse(status_code=500, content=body.model_dump())

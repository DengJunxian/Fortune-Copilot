from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = dict(details or {})


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": _request_id(request),
                "details": details,
            }
        },
    )


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return _response(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Rejected financial payloads can contain PII. Return only structural
        # validation evidence, never the submitted value or exception object.
        safe_details = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": str(error.get("msg", "请求数据无效")),
                "type": str(error.get("type", "validation_error")),
            }
            for error in exc.errors()
        ]
        return _response(
            request,
            status_code=422,
            code="validation_error",
            message="请求数据校验失败",
            details=safe_details,
        )

    @app.exception_handler(StarletteHTTPException)
    @app.exception_handler(HTTPException)
    async def http_error_handler(
        request: Request, exc: StarletteHTTPException | HTTPException
    ) -> JSONResponse:
        message = str(exc.detail) if exc.detail else "请求无法处理"
        return _response(
            request,
            status_code=exc.status_code,
            code="http_error",
            message=message,
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Exception messages and trace locals can contain submitted identity or
        # financial values. Keep the operational log structural and redacted.
        logger.error(
            "Unhandled application error type=%s",
            type(exc).__name__,
            extra={"request_id": _request_id(request)},
        )
        return _response(
            request,
            status_code=500,
            code="internal_error",
            message="服务暂时无法处理请求",
        )

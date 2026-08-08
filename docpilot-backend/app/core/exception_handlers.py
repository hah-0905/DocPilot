import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppException


logger = logging.getLogger(__name__)


def error_response(
        code: int,
        message: str,
        data: object | None = None,
        status_code: int = 400,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "code": code,
            "message": message,
            "data": data,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(
        request: Request,
        exc: AppException,
    ) -> JSONResponse:
        logger.warning(
            "Business exception | method=%s path=%s code=%s message=%s",
            request.method,
            request.url.path,
            exc.code,
            exc.message,
        )

        return error_response(
            code=exc.code,
            message=exc.message,
            data=exc.data,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = []

        for error in exc.errors():
            loc = ".".join(str(item) for item in error.get("loc", []))
            msg = error.get("msg", "Invalid request")

            errors.append(
                {
                    "field": loc,
                    "error": msg,
                }
            )

        logger.warning(
            "Validation error | method=%s path=%s errors=%s",
            request.method,
            request.url.path,
            errors,
        )

        return error_response(
            code=422,
            message="Validation error",
            data=errors,
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        logger.warning(
            "HTTP exception | method=%s path=%s status_code=%s detail=%s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.detail,
        )

        return error_response(
            code=exc.status_code,
            message=str(exc.detail),
            data=None,
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception | method=%s path=%s",
            request.method,
            request.url.path,
        )

        return error_response(
            code=500,
            message="Internal server error",
            data=None,
            status_code=500,
        )

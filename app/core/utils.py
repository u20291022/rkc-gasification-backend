from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.schemas.base import BaseResponse
from app.core.logging import get_logger, categorize_log, LogCategory
from typing import Optional, Any

logger = get_logger("utils")


def create_response(data, message="Успех", ok=True):
    logger.debug(
        categorize_log(f"Creating response: {message}", LogCategory.DEBUG),
        extra={"ok": ok, "has_data": data is not None},
    )
    return BaseResponse(ok=ok, message=message, data=data)


def create_error_response(status_code: int, detail: str, data=None):
    logger.error(
        categorize_log(f"Error response: {detail}", LogCategory.ERROR),
        extra={"status_code": status_code},
    )
    return JSONResponse(
        status_code=status_code,
        content=BaseResponse(ok=False, message=detail, data=data).model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        categorize_log(f"HTTP Exception: {exc.detail}", LogCategory.ERROR),
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "request_id": request_id,
        },
    )
    return create_error_response(exc.status_code, exc.detail)


async def general_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        categorize_log(f"Unhandled exception: {str(exc)}", LogCategory.ERROR),
        extra={
            "path": request.url.path,
            "request_id": request_id,
            "exception_type": type(exc).__name__,
        },
        exc_info=True,
    )
    return create_error_response(500, "Internal server error")


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "unknown")
    errors = []
    for error in exc.errors():
        loc = ".".join([str(item) for item in error["loc"]])
        errors.append(f"{loc}: {error['msg']}")
    error_detail = "Ошибка валидации данных:\n" + "\n".join(errors)
    logger.warning(
        categorize_log(f"Validation error in request", LogCategory.ERROR),
        extra={
            "path": request.url.path,
            "request_id": request_id,
            "validation_errors": errors,
        },
    )
    return create_error_response(422, error_detail)


def log_db_operation(
    operation: str, model: str, extra: Optional[dict[str, Any]] = None
):
    logger.info(
        categorize_log(f"DB {operation}: {model}", LogCategory.DB), extra=extra or {}
    )


async def record_activity(email: str, session_id: str):
    """Записывает или обновляет активность пользователя"""
    if not session_id:
        return
    from app.models.models import Activity

    try:
        activity = await Activity.get_or_none(session_id=session_id)
        if activity:
            activity.activity_count += 1
            await activity.save(update_fields=["activity_count"])
        else:
            await Activity.create(session_id=session_id, email=email, activity_count=1)
        log_db_operation(
            "activity",
            "Activity",
            {
                "session_id": session_id,
                "email": email,
                "action": "increment" if activity else "create",
            },
        )
    except Exception as e:
        logger.error(f"Error recording activity: {str(e)}", exc_info=True)

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from tortoise.contrib.fastapi import register_tortoise
from app.core.config import TORTOISE_ORM, settings
from app.api.v1 import api_v1_router
from app.core.utils import (
    general_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.core.logging import setup_logging, get_logger, categorize_log, LogCategory
from app.core.middleware import setup_middlewares

logger = None


async def lifespan(app: FastAPI):
    global logger
    setup_logging(settings.LOG_LEVEL)
    logger = get_logger("main")
    logger.info(categorize_log("Starting up application", LogCategory.INIT))
    yield
    logger.info(categorize_log("Shutting down application", LogCategory.INIT))


app = FastAPI(
    title="RKC Gazification API",
    description="API для работы с данными газификации",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)
setup_middlewares(app)
app.include_router(api_v1_router, prefix="/v1")
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
register_tortoise(
    app,
    config=TORTOISE_ORM,
    generate_schemas=False,
    add_exception_handlers=True,
)

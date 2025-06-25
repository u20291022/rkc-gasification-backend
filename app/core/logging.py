import logging
import sys
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
from app.core.config import settings


class LogCategory(Enum):
    INIT = "init"
    HTTP = "http"
    DB = "db"
    ERROR = "error"
    GENERAL = "general"
    DEBUG = "debug"


class DetailedFileFormatter(logging.Formatter):
    """A formatter that includes additional request/response details for file logging."""

    def format(self, record):
        log_message = super().format(record)
        extra_details = []
        if hasattr(record, "request_id"):
            extra_details.append(f"Request ID: {record.request_id}")
        if hasattr(record, "client_ip"):
            extra_details.append(f"Client IP: {record.client_ip}")
        if hasattr(record, "headers") and record.headers:
            extra_details.append(f"Headers: {self._format_dict(record.headers)}")
        if hasattr(record, "query_params") and record.query_params:
            extra_details.append(
                f"Query Params: {self._format_dict(record.query_params)}"
            )
        if hasattr(record, "request_body") and record.request_body:
            extra_details.append(
                f"Request Body: {self._format_dict(record.request_body)}"
            )
        if hasattr(record, "response_body") and record.response_body:
            extra_details.append(
                f"Response Body: {self._format_dict(record.response_body)}"
            )
        if hasattr(record, "status_code"):
            extra_details.append(f"Status Code: {record.status_code}")
        if hasattr(record, "processing_time_ms"):
            extra_details.append(f"Processing Time: {record.processing_time_ms}ms")
        if extra_details:
            log_message += "\n" + "\n".join(extra_details)
        return log_message

    def _format_dict(self, data):
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except:
            return str(data)


def setup_logging(log_level: str = "INFO") -> None:
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_level_obj = getattr(logging, log_level)
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level_obj)
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    console_handler.setLevel(log_level_obj)
    root_logger.addHandler(console_handler)
    file_handler = logging.FileHandler(
        logs_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"
    )
    file_handler.setFormatter(DetailedFileFormatter(log_format))
    file_handler.setLevel(log_level_obj)
    root_logger.addHandler(file_handler)
    error_file_handler = logging.FileHandler(
        logs_dir / f"errors_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(DetailedFileFormatter(log_format))
    root_logger.addHandler(error_file_handler)
    if (
        settings.ENABLE_TELEGRAM_LOGGING
        and settings.TELEGRAM_BOT_TOKEN
        and settings.TELEGRAM_CHAT_ID
    ):
        from app.core.telegram_logging import TelegramLogHandler

        telegram_handler = TelegramLogHandler(
            bot_token=settings.TELEGRAM_BOT_TOKEN, chat_id=settings.TELEGRAM_CHAT_ID
        )
        telegram_handler.setLevel(logging.INFO)
        root_logger.addHandler(telegram_handler)
        logging.getLogger("app").info(
            categorize_log("Telegram logging initialized", LogCategory.INIT)
        )
    for logger_name in ["uvicorn", "uvicorn.access", "watchfiles", "tortoise", "httpx"]:
        mod_logger = logging.getLogger(logger_name)
        if settings.LOG_SQL_QUERIES and logger_name == "tortoise":
            mod_logger.setLevel(log_level_obj)
        else:
            mod_logger.handlers = []
            mod_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def categorize_log(message: str, category: LogCategory) -> str:
    """Add a category marker to a log message."""
    return f"[{category.value}] {message}"

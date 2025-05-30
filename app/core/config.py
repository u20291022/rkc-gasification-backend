from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    # Настройки для базы данных addresses (ГАР)
    ADDRESSES_DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/addresses"
    LOG_LEVEL: str = "INFO"
    ENABLE_REQUEST_LOGGING: bool = True
    LOG_SQL_QUERIES: bool = False
    
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_LOG_LEVEL: str = "ERROR"
    ENABLE_TELEGRAM_LOGGING: bool = False

    class Config:
        env_file = ".env"

settings = Settings()

# Конфигурация для Tortoise ORM (основная база данных)
TORTOISE_ORM = {
    "connections": {"default": settings.DATABASE_URL},
    "apps": {
        "models": {
            "models": ["app.models", "aerich.models"],
            "default_connection": "default",
        },
    },
    "use_tz": True,
    "timezone": "UTC"
}

# Глобальная переменная для пула соединений addresses
addresses_connection_pool = None
# RKC Газификация API

Сервис API для сбора и управления данными о газификации.

## Содержание

- [Требования](#требования)
- [Установка](#установка)
- [Запуск](#запуск)
- [API Endpoints](#api-endpoints)
- [Структура проекта](#структура-проекта)

## Требования

- Python 3.10+
- FastAPI
- Tortoise ORM
- PostgreSQL

## Установка

1. Клонировать репозиторий
```bash
git clone <repo-url>
cd rkc-gazik-quiz-backend
```

2. Установить зависимости
```bash
pip install -r requirements.txt
```

3. Создать файл .env в корне проекта
```
DATABASE_URL=postgres://username:password@localhost:5432/database_name
LOG_LEVEL=INFO
ENABLE_REQUEST_LOGGING=True
LOG_SQL_QUERIES=False
```

## Запуск

```bash
uvicorn main:app --reload
```

Сервис будет доступен по адресу http://localhost:8000

Документация Swagger UI: http://localhost:8000/docs

## API Endpoints

Базовый адрес: `/v1`

### Муниципалитеты

- `GET /mo` - Получить список муниципалитетов

### Районы

- `GET /mo/{mo_id}/district` - Получить список районов по ID муниципалитета

### Улицы

- `GET /mo/{mo_id}/district/{district_id}/street` - Получить список улиц по району

### Дома

- `GET /mo/{mo_id}/district/{district_id}/street/{street_id}/house` - Получить список домов

### Квартиры

- `GET /mo/{mo_id}/district/{district_id}/street/{street_id}/house/{house_id}/flat` - Получить список квартир

### Добавление данных

- `POST /add` - Добавить новый адрес
- `POST /upload` - Загрузить данные о газификации

## Структура проекта

```
app/
├── api/
│   └── v1/
│       ├── endpoints/
│       │   └── gazification/
│       └── router.py
├── core/
│   ├── config.py
│   ├── exceptions.py
│   ├── logging.py
│   ├── middleware.py
│   └── utils.py
├── models/
│   └── models.py
└── schemas/
    ├── base.py
    └── gazification.py
```

Модели описаны в файле `app/models/models.py`.
Схемы данных для API описаны в файле `app/schemas/gazification.py`.

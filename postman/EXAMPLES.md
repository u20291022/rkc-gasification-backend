# Примеры запросов и ответов - Address Hints API

## Быстрый старт

### 1. Проверка состояния сервиса

**Запрос:**
```http
GET /v1/addresses/health
```

**Ответ:**
```json
{
  "ok": true,
  "message": "Сервис адресных подсказок работает корректно",
  "data": {
    "database_status": "connected",
    "connection_pool": {
      "size": 5,
      "max_size": 10
    }
  }
}
```

---

### 2. Получение муниципальных образований

**Запрос:**
```http
GET /v1/addresses/municipalities?search=Москва&limit=10&offset=0
```

**Ответ:**
```json
{
  "ok": true,
  "message": "Найдено 2 муниципальных образования",
  "data": {
    "items": [
      {
        "id": 1,
        "name": "г Москва",
        "type_name": "г",
        "type_full_name": "город",
        "merged_entities": [
          {
            "id": 2,
            "name": "г.о. Москва",
            "type_name": "г.о.",
            "type_full_name": "городской округ"
          }
        ]
      }
    ],
    "total": 2,
    "limit": 10,
    "offset": 0
  }
}
```

---

### 3. Получение улиц в городе

**Запрос:**
```http
GET /v1/addresses/streets?municipality_id=1&search=Ленина&limit=20&offset=0
```

**Ответ:**
```json
{
  "ok": true,
  "message": "Найдено 15 улиц",
  "data": {
    "items": [
      {
        "id": 101,
        "object_id": "abc123",
        "name": "ул Ленина",
        "type_name": "ул",
        "type_full_name": "улица",
        "houses_count": 156
      },
      {
        "id": 102,
        "object_id": "def456",
        "name": "пр-кт Ленина",
        "type_name": "пр-кт",
        "type_full_name": "проспект",
        "houses_count": 89
      }
    ],
    "total": 15,
    "limit": 20,
    "offset": 0
  }
}
```

---

### 4. Получение домов на улице

**Запрос:**
```http
GET /v1/addresses/houses?street_id=101&search=10&limit=50&offset=0
```

**Ответ:**
```json
{
  "ok": true,
  "message": "Найдено 8 домов",
  "data": {
    "items": [
      {
        "id": 1001,
        "object_id": "house123",
        "name": "д 10",
        "number": "10",
        "type_name": "д",
        "type_full_name": "дом",
        "apartments_count": 45
      },
      {
        "id": 1002,
        "object_id": "house124",
        "name": "д 10А",
        "number": "10А",
        "type_name": "д",
        "type_full_name": "дом",
        "apartments_count": 32
      }
    ],
    "total": 8,
    "limit": 50,
    "offset": 0
  }
}
```

---

### 5. Получение квартир в доме

**Запрос:**
```http
GET /v1/addresses/apartments?house_id=1001&search=15&limit=50&offset=0
```

**Ответ:**
```json
{
  "ok": true,
  "message": "Найдено 3 квартиры",
  "data": {
    "items": [
      {
        "id": 10001,
        "object_id": "apt123",
        "name": "кв 15",
        "number": "15",
        "type_name": "кв",
        "type_full_name": "квартира",
        "rooms_count": 2
      },
      {
        "id": 10002,
        "object_id": "apt124",
        "name": "кв 150",
        "number": "150",
        "type_name": "кв",
        "type_full_name": "квартира",
        "rooms_count": 3
      }
    ],
    "total": 3,
    "limit": 50,
    "offset": 0
  }
}
```

---

### 6. Проверка структуры адресов

**Запрос:**
```http
GET /v1/addresses/address-structure/1
```

**Ответ (городская структура):**
```json
{
  "ok": true,
  "message": "Структура адресных данных определена",
  "data": {
    "municipality_id": 1,
    "municipality_name": "г Москва",
    "has_streets": true,
    "has_settlements": false,
    "address_type": "urban",
    "suggested_flow": [
      "municipality",
      "street",
      "house",
      "apartment",
      "room"
    ],
    "statistics": {
      "streets_count": 1245,
      "settlements_count": 0,
      "total_houses": 15678
    }
  }
}
```

**Ответ (сельская структура):**
```json
{
  "ok": true,
  "message": "Структура адресных данных определена",
  "data": {
    "municipality_id": 2,
    "municipality_name": "Пушкинский м.р.",
    "has_streets": false,
    "has_settlements": true,
    "address_type": "rural",
    "suggested_flow": [
      "municipality",
      "settlement",
      "rural_house"
    ],
    "statistics": {
      "streets_count": 0,
      "settlements_count": 45,
      "total_houses": 892
    }
  }
}
```

---

### 7. Получение сельских населённых пунктов

**Запрос:**
```http
GET /v1/addresses/settlements?municipality_id=2&search=село&limit=20&offset=0
```

**Ответ:**
```json
{
  "ok": true,
  "message": "Найдено 12 населенных пунктов",
  "data": {
    "items": [
      {
        "id": 201,
        "object_id": "settlement123",
        "name": "с Петровское",
        "type_name": "с",
        "type_full_name": "село",
        "houses_count": 67
      },
      {
        "id": 202,
        "object_id": "settlement124",
        "name": "с Ивановское",
        "type_name": "с",
        "type_full_name": "село",
        "houses_count": 34
      }
    ],
    "total": 12,
    "limit": 20,
    "offset": 0
  }
}
```

---

### 8. Получение сельских домов

**Запрос:**
```http
GET /v1/addresses/rural-houses?settlement_id=settlement123&search=5&limit=50&offset=0
```

**Ответ:**
```json
{
  "ok": true,
  "message": "Найдено 4 дома",
  "data": {
    "items": [
      {
        "id": 2001,
        "object_id": "rural_house123",
        "name": "д 5",
        "number": "5",
        "type_name": "д",
        "type_full_name": "дом"
      },
      {
        "id": 2002,
        "object_id": "rural_house124",
        "name": "д 5А",
        "number": "5А",
        "type_name": "д",
        "type_full_name": "дом"
      }
    ],
    "total": 4,
    "limit": 50,
    "offset": 0
  }
}
```

---

## Типичные сценарии использования

### Сценарий 1: Полный городской адрес

1. **Выбор города:** `GET /municipalities?search=Москва`
2. **Выбор улицы:** `GET /streets?municipality_id=1&search=Ленина`
3. **Выбор дома:** `GET /houses?street_id=101&search=10`
4. **Выбор квартиры:** `GET /apartments?house_id=1001&search=15`
5. **Выбор комнаты:** `GET /rooms?apartment_id=10001`

**Результат:** г Москва, ул Ленина, д 10, кв 15, комн 1

### Сценарий 2: Сельский адрес

1. **Выбор района:** `GET /municipalities?search=Пушкинский`
2. **Проверка структуры:** `GET /address-structure/2`
3. **Выбор села:** `GET /settlements?municipality_id=2&search=Петровское`
4. **Выбор дома:** `GET /rural-houses?settlement_id=settlement123&search=5`

**Результат:** Пушкинский м.р., с Петровское, д 5

### Сценарий 3: Автодополнение

Для реализации автодополнения в UI:

```javascript
// Пример для поиска улиц
const searchStreets = async (municipalityId, query) => {
  const response = await fetch(
    `/v1/addresses/streets?municipality_id=${municipalityId}&search=${query}&limit=10`
  );
  const data = await response.json();
  return data.data.items;
};
```

---

## Обработка ошибок

### Ошибка базы данных
```json
{
  "ok": false,
  "message": "Ошибка базы данных: connection timeout",
  "detail": "Превышено время ожидания соединения с базой данных addresses"
}
```

### Некорректные параметры
```json
{
  "ok": false,
  "message": "Validation error",
  "detail": [
    {
      "loc": ["query", "municipality_id"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Не найдено данных
```json
{
  "ok": true,
  "message": "Улицы не найдены",
  "data": {
    "items": [],
    "total": 0,
    "limit": 50,
    "offset": 0
  }
}
```

---

## Советы по оптимизации

### 1. Используйте пагинацию
```http
GET /streets?municipality_id=1&limit=20&offset=0
```

### 2. Применяйте фильтрацию
```http
GET /houses?street_id=101&search=10  # Только дома с номером содержащим "10"
```

### 3. Проверяйте структуру перед запросами
```http
GET /address-structure/1  # Узнайте, есть ли улицы или только сёла
```

### 4. Кэшируйте результаты
Результаты запросов municipalities и address-structure можно кэшировать на длительное время.

### 5. Обрабатывайте группировку
Учитывайте поле `merged_entities` для отображения связанных административных единиц.

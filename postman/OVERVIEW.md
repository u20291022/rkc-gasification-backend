# Postman коллекция Address Hints API - Обзор

## 📋 Созданные файлы

### 1. 🔧 Основная коллекция
**Файл:** `RKC_Address_Hints_API.postman_collection.json`  
**Описание:** Полная коллекция с всеми endpoints и автоматизированными тестами

### 2. 🌍 Окружения (Environments)
- **Development:** `RKC_Address_Environment.postman_environment.json`
- **Production:** `RKC_Address_Production.postman_environment.json`

### 3. 📚 Документация
- **README.md** - подробная инструкция по установке и использованию
- **EXAMPLES.md** - примеры запросов и ответов
- **OVERVIEW.md** - этот файл с общим обзором

---

## 🚀 Быстрый старт

### Импорт в Postman

1. **Коллекция:**
   - Откройте Postman → Import
   - Выберите `RKC_Address_Hints_API.postman_collection.json`

2. **Окружение для разработки:**
   - Settings ⚙️ → Manage Environments → Import
   - Выберите `RKC_Address_Environment.postman_environment.json`
   - Активируйте окружение "RKC Address Hints - Development"

3. **Первый запрос:**
   ```
   GET {{baseUrl}}/{{apiVersion}}/addresses/health
   ```

---

## 📊 Структура коллекции

### Address Hints (Основные endpoints)
- ✅ Health Check
- 🏙️ Get Municipalities / Search
- 🏛️ Get Address Structure
- 🛣️ Get Streets / Search Streets  
- 🏠 Get Houses / Search Houses
- 🚪 Get Apartments / Search Apartments
- 🪑 Get Rooms
- 🏘️ Get Settlements / Search Settlements
- 🏚️ Get Rural Houses / Search Rural Houses

### Typical Use Cases (Готовые сценарии)
- **🏙️ City Address Flow:** Город → Улица → Дом → Квартира → Комната
- **🏘️ Rural Address Flow:** Район → Населённый пункт → Сельский дом

---

## 🔬 Автоматизация и тесты

### Автоматические тесты
```javascript
✅ Status code is 200
✅ Response time is acceptable (< 5s) 
✅ Response has correct structure
✅ Items have correct structure
```

### Автоматическое сохранение переменных
```javascript
// После запроса municipalities:
selectedMunicipalityId = 123

// После запроса streets:
selectedStreetId = 456

// И так далее для создания цепочки запросов
```

### Логирование
```
🚀 Выполняется запрос: GET /v1/addresses/municipalities
🏙️ Выбран муниципалитет ID: 123 (г Москва)
📊 Найдено элементов: 45
⏱️ Время ответа: 234ms
```

---

## 🎯 Типичные сценарии использования

### 1. Тестирование API во время разработки
1. Запустите локальный сервер
2. Используйте окружение "Development"
3. Выполните Health Check
4. Тестируйте endpoints по одному

### 2. Демонстрация функциональности
1. Используйте папку "Typical Use Cases"
2. Запустите "City Address Flow" для городских адресов
3. Запустите "Rural Address Flow" для сельских адресов
4. Покажите автоматическое связывание запросов

### 3. Нагрузочное тестирование
1. Используйте Collection Runner
2. Установите количество итераций
3. Добавьте задержки между запросами
4. Мониторьте время ответа

### 4. Интеграционное тестирование
1. Создайте тестовые данные в базе
2. Запустите всю коллекцию
3. Проверьте результаты автоматических тестов
4. Валидируйте структуру ответов

---

## 🔄 Переменные окружения

| Переменная | Development | Production |
|------------|-------------|------------|
| `baseUrl` | `http://localhost:8000` | `https://api.rkc-gazification.ru` |
| `apiVersion` | `v1` | `v1` |

**Динамические переменные** (автоматически заполняются):
- `selectedMunicipalityId`
- `selectedStreetId` 
- `selectedHouseId`
- `selectedApartmentId`
- `selectedSettlementObjectId`
- `selectedRuralHouseId`

---

## 🛠️ Кастомизация

### Добавление новых тестов
```javascript
pm.test("Custom test", function () {
    const jsonData = pm.response.json();
    pm.expect(jsonData.data.items.length).to.be.above(0);
});
```

### Модификация базового URL
```javascript
// Pre-request Script
pm.environment.set("baseUrl", "https://staging-api.example.com");
```

### Добавление аутентификации
```javascript
// Pre-request Script для добавления токена
pm.request.headers.add({
    key: "Authorization",
    value: "Bearer " + pm.environment.get("authToken")
});
```

---

## 🐛 Диагностика проблем

### Ошибки подключения
1. Проверьте переменную `baseUrl`
2. Убедитесь, что сервер запущен
3. Выполните Health Check

### Неактуальные данные  
1. Очистите переменные окружения
2. Выполните запросы заново
3. Проверьте данные в базе

### Медленные ответы
1. Уменьшите `limit` в запросах
2. Добавьте более специфичный `search`
3. Проверьте индексы в БД

---

## 📈 Метрики и мониторинг

### Отслеживаемые метрики
- Время ответа (`lastResponseTime`)
- Количество найденных элементов (`totalItemsFound`)
- Статус соединения с БД (через Health Check)

### Рекомендуемые SLA
- Время ответа: < 1 секунда для простых запросов
- Время ответа: < 3 секунды для сложных запросов с поиском
- Доступность: 99.9%

---

## 🔗 Связанные файлы

- **Backend документация:** `docs/Методы v1/API Адресные подсказки.md`
- **Схемы данных:** `app/schemas/addresses.py`
- **API endpoints:** `app/api/v1/endpoints/addresses/`
- **Конфигурация:** `app/core/config.py`

---

## 🎉 Заключение

Postman коллекция предоставляет полный набор инструментов для:
- ✅ Тестирования всех endpoints
- ✅ Демонстрации функциональности
- ✅ Автоматизации процессов
- ✅ Мониторинга производительности
- ✅ Интеграционного тестирования

Коллекция готова к использованию "из коробки" и может быть легко адаптирована под конкретные нужды проекта.
